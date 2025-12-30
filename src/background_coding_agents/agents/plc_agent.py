"""
PLC Coding Agent
Transforms PLC code based on natural language prompts.
Inspired by Spotify's background coding agent architecture.

Supports multiple LLM backends including local models for air-gapped environments.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from background_coding_agents.config import get_settings
from background_coding_agents.llm import (
    BaseLLMProvider,
    LLMProviderFactory,
    Message,
    MessageRole,
    ToolDefinition,
    create_provider,
)
from background_coding_agents.logging import AuditLogger, LogContext, get_logger
from background_coding_agents.models import (
    AgentConfig,
    AgentResult,
    AgentStatus,
    ExecutionPlan,
    PLCChange,
    PlanStep,
    SiteConfig,
    VerificationResult,
    VerificationType,
)

logger = get_logger(__name__)


@dataclass
class AgentContext:
    """Runtime context for agent execution."""

    site_config: SiteConfig
    agent_config: AgentConfig
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    start_time: float = field(default_factory=time.time)
    turns_taken: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


class PLCAgent:
    """
    Background coding agent for PLC code transformations.

    Key Design Principles (from Spotify Part 3):
    1. Focused: Only does code changes, nothing else
    2. Sandboxed: Limited permissions and tool access
    3. Guided: Strong verification loops
    4. Flexible: Works with cloud and local LLMs

    Supports:
    - Multiple LLM backends (Anthropic, OpenAI, llama.cpp, vLLM)
    - Local models: GLM-4.7, MiniMax-M2.1 for air-gapped environments
    - Configurable tools and verification
    - Structured logging and audit trail
    - Token usage tracking
    """

    def __init__(
        self,
        site_config: SiteConfig | dict,
        agent_config: AgentConfig | None = None,
        llm_provider: BaseLLMProvider | None = None,
    ):
        """
        Initialize the PLC Agent.

        Args:
            site_config: Target site configuration
            agent_config: Agent behavior configuration (uses defaults if None)
            llm_provider: LLM provider instance (auto-creates if None)
        """
        # Convert dict to model if needed
        if isinstance(site_config, dict):
            site_config = SiteConfig(**site_config)

        self.site_config = site_config
        self.agent_config = agent_config or self._default_agent_config()
        self._llm_provider = llm_provider
        self._audit_logger = AuditLogger()

        # Runtime state
        self.changes: list[PLCChange] = []
        self.context_window: list[Message] = []
        self.result: AgentResult | None = None

    def _default_agent_config(self) -> AgentConfig:
        """Create default agent configuration from settings."""
        settings = get_settings()
        return AgentConfig(
            llm_provider=settings.llm.provider,
            llm_model=settings.llm.model,
            llm_base_url=settings.llm.base_url,
            max_turns=settings.agent.max_turns,
            max_retries=settings.agent.max_retries,
            timeout_seconds=settings.agent.timeout,
            tools=settings.agent.tools,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
        )

    async def _get_llm_provider(self) -> BaseLLMProvider:
        """Get or create the LLM provider."""
        if self._llm_provider is None:
            settings = get_settings()
            api_key = settings.get_llm_api_key(self.agent_config.llm_provider)

            self._llm_provider = LLMProviderFactory.create(
                provider=self.agent_config.llm_provider,
                model=self.agent_config.llm_model,
                api_key=api_key,
                base_url=self.agent_config.llm_base_url,
                temperature=self.agent_config.temperature,
                max_tokens=self.agent_config.max_tokens,
            )
            await self._llm_provider.initialize()

        return self._llm_provider

    async def execute(self, prompt: str) -> AgentResult:
        """
        Execute the agent with a given prompt.

        Process:
        1. Read relevant files
        2. Plan changes
        3. Make edits iteratively
        4. Verify after each edit
        5. Complete when tests pass or max turns reached

        Args:
            prompt: Natural language task description

        Returns:
            AgentResult with changes, verification outcomes, and metadata
        """
        task_id = str(uuid.uuid4())[:12]
        ctx = AgentContext(
            site_config=self.site_config,
            agent_config=self.agent_config,
        )

        self.result = AgentResult(
            task_id=task_id,
            site_name=self.site_config.name,
            status=AgentStatus.IDLE,
        )

        with LogContext(
            correlation_id=ctx.correlation_id,
            site_name=self.site_config.name,
            task_id=task_id,
        ):
            logger.info(
                "Agent starting execution",
                prompt_length=len(prompt),
                max_turns=self.agent_config.max_turns,
                llm_provider=self.agent_config.llm_provider.value,
            )

            try:
                # Initialize LLM provider
                llm = await self._get_llm_provider()
                self.result.llm_provider = llm.provider_name
                self.result.llm_model = llm.config.model

                # Phase 1: Discovery and Planning
                self.result.status = AgentStatus.PLANNING
                relevant_files = await self._discover_relevant_files(prompt, llm)
                plan = await self._create_plan(prompt, relevant_files, llm)
                self.result.plan = plan

                # Phase 2: Execution with verification loops
                self.result.status = AgentStatus.EXECUTING
                await self._execute_plan(plan, llm, ctx)

                # Phase 3: Final verification
                self.result.status = AgentStatus.VERIFYING
                verification_passed = await self._final_verification()
                self.result.all_verifications_passed = verification_passed

                # Complete
                self.result.turns_taken = ctx.turns_taken
                self.result.total_input_tokens = ctx.total_input_tokens
                self.result.total_output_tokens = ctx.total_output_tokens
                self.result.changes = [c.model_dump() for c in self.changes]
                self.result.complete(success=verification_passed)

                logger.info(
                    "Agent execution completed",
                    success=self.result.success,
                    changes_made=len(self.changes),
                    turns_taken=ctx.turns_taken,
                    total_tokens=ctx.total_input_tokens + ctx.total_output_tokens,
                )

            except asyncio.TimeoutError:
                self.result.fail("Execution timeout exceeded")
                logger.error("Agent execution timed out")

            except Exception as e:
                import traceback

                self.result.fail(str(e), traceback.format_exc())
                logger.exception("Agent execution failed", error=str(e))

            return self.result

    async def _discover_relevant_files(
        self, prompt: str, llm: BaseLLMProvider
    ) -> list[str]:
        """
        Find files relevant to the task.

        Uses LLM to identify which files should be examined based on
        the prompt and repository structure.
        """
        repo_path = Path(self.site_config.repo_path)

        # Get list of files in repository
        available_files = await self._list_repository_files(repo_path)

        if not available_files:
            # Return default files for simulation
            return [
                str(repo_path / "src/main_program.st"),
                str(repo_path / "src/safety_interlocks.st"),
                str(repo_path / "config/io_mapping.xml"),
            ]

        # Use LLM to select relevant files
        discovery_prompt = f"""Given this task for a PLC system:

{prompt}

Which of these files are most relevant? List only the file paths, one per line:

{chr(10).join(available_files[:50])}  # Limit to avoid context overflow

Respond with just the file paths, nothing else."""

        try:
            response = await llm.generate(
                messages=[Message(role=MessageRole.USER, content=discovery_prompt)],
                max_tokens=500,
            )

            # Parse file paths from response
            if response.content:
                files = [
                    line.strip()
                    for line in response.content.split("\n")
                    if line.strip() and not line.startswith("#")
                ]
            else:
                files = []

            logger.info("Discovered relevant files", file_count=len(files))
            return files[:10]  # Limit to avoid context overflow

        except Exception as e:
            logger.warning("File discovery failed, using defaults", error=str(e))
            return [
                str(repo_path / "src/main_program.st"),
                str(repo_path / "src/safety_interlocks.st"),
            ]

    async def _list_repository_files(self, repo_path: Path) -> list[str]:
        """List files in the repository."""
        if not repo_path.exists():
            return []

        files = []
        try:
            for path in repo_path.rglob("*"):
                if path.is_file() and not any(
                    part.startswith(".") for part in path.parts
                ):
                    files.append(str(path))
        except Exception as e:
            logger.warning("Failed to list repository files", error=str(e))

        return files

    async def _create_plan(
        self, prompt: str, files: list[str], llm: BaseLLMProvider
    ) -> ExecutionPlan:
        """
        Create execution plan using LLM.

        Generates a step-by-step plan before making any changes.
        """
        plan = ExecutionPlan(
            task_id=self.result.task_id if self.result else str(uuid.uuid4())[:12],
            prompt=prompt,
            relevant_files=files,
        )

        planning_prompt = f"""You are planning changes to a PLC system at {self.site_config.name}.

## Site Information
- PLC Type: {self.site_config.plc_type.value}
- Safety Rating: {self.site_config.safety_rating.value}
- Firmware: {self.site_config.firmware_version}

## Task
{prompt}

## Relevant Files
{chr(10).join(f"- {f}" for f in files)}

## Instructions
Create a step-by-step plan to accomplish this task. Each step should be:
1. Specific and actionable
2. Focused on a single file or small change
3. Verifiable after completion

Format your response as a numbered list:
1. [action] - [file] - [description]
2. [action] - [file] - [description]
..."""

        try:
            response = await llm.generate(
                messages=[Message(role=MessageRole.USER, content=planning_prompt)],
                max_tokens=1000,
            )

            # Parse steps from response
            if response.content:
                steps = self._parse_plan_steps(response.content)
                plan.steps = steps
                plan.files_to_modify = list(set(s.target_file for s in steps if s.target_file))

                logger.info("Created execution plan", step_count=len(steps))
            else:
                logger.warning("LLM returned empty content for planning")
                raise ValueError("Empty plan response")

        except Exception as e:
            logger.warning("Plan creation failed, using default", error=str(e))
            # Create minimal default plan
            plan.steps = [
                PlanStep(
                    step_number=1,
                    action="review",
                    target_file=files[0] if files else None,
                    description="Review and update code per task requirements",
                )
            ]

        return plan

    def _parse_plan_steps(self, content: str) -> list[PlanStep]:
        """Parse plan steps from LLM response."""
        steps = []
        for i, line in enumerate(content.split("\n"), 1):
            line = line.strip()
            if not line or not line[0].isdigit():
                continue

            # Try to parse "N. action - file - description"
            try:
                # Remove number prefix
                text = line.split(".", 1)[-1].strip()
                parts = text.split(" - ", 2)

                action = parts[0].strip() if len(parts) > 0 else "update"
                target_file = parts[1].strip() if len(parts) > 1 else None
                description = parts[2].strip() if len(parts) > 2 else text

                steps.append(
                    PlanStep(
                        step_number=len(steps) + 1,
                        action=action,
                        target_file=target_file,
                        description=description,
                    )
                )
            except Exception:
                # Fallback: use whole line as description
                steps.append(
                    PlanStep(
                        step_number=len(steps) + 1,
                        action="update",
                        description=line,
                    )
                )

        return steps[:10]  # Limit steps

    async def _execute_plan(
        self, plan: ExecutionPlan, llm: BaseLLMProvider, ctx: AgentContext
    ) -> None:
        """Execute the plan step by step."""
        for step in plan.steps:
            if ctx.turns_taken >= self.agent_config.max_turns:
                logger.warning(
                    "Reached max turns",
                    max_turns=self.agent_config.max_turns,
                    completed_steps=ctx.turns_taken,
                )
                break

            step.status = "in_progress"
            step.started_at = datetime.utcnow()

            try:
                # Make the change
                change = await self._make_change(step, llm, ctx)

                if change:
                    self.changes.append(change)
                    ctx.turns_taken += 1

                    # Quick verification (inner loop)
                    if self.agent_config.enable_quick_verify:
                        if not await self._quick_verify(change):
                            logger.info("Quick verification failed, attempting fix")
                            await self._attempt_fix(change, llm, ctx)

                step.status = "completed"
                step.completed_at = datetime.utcnow()

            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                step.completed_at = datetime.utcnow()
                logger.error("Step execution failed", step=step.step_number, error=str(e))

    async def _make_change(
        self, step: PlanStep, llm: BaseLLMProvider, ctx: AgentContext
    ) -> PLCChange | None:
        """
        Execute a single change step.

        Uses LLM to generate the actual code transformation.
        """
        # Read current file content
        old_code = await self._read_file(step.target_file)

        change_prompt = f"""You are modifying PLC code for {self.site_config.name}.

## Current Code
```
{old_code}
```

## Task
{step.description}

## Safety Requirements
- Do NOT modify emergency stop logic
- Do NOT modify certified safety modules
- Maintain SIL-{self.site_config.safety_rating.level} compliance

## Instructions
Provide the modified code. Only include the code, no explanations."""

        try:
            start_time = time.time()
            response = await llm.generate(
                messages=[Message(role=MessageRole.USER, content=change_prompt)],
                max_tokens=2000,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            # Track token usage
            if response.usage:
                ctx.total_input_tokens += response.input_tokens
                ctx.total_output_tokens += response.output_tokens

                self._audit_logger.log_llm_call(
                    provider=llm.provider_name,
                    model=llm.config.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    latency_ms=latency_ms,
                    purpose="code_transformation",
                )

            # Extract code from response
            new_code = self._extract_code(response.content)

            change = PLCChange(
                file_path=step.target_file or "unknown",
                old_code=old_code,
                new_code=new_code,
                reason=step.description,
                agent_turn=ctx.turns_taken + 1,
            )

            logger.info(
                "Made code change",
                file=step.target_file,
                lines_added=change.lines_added,
                lines_removed=change.lines_removed,
            )

            return change

        except Exception as e:
            logger.error("Failed to make change", error=str(e))
            return None

    async def _read_file(self, file_path: str | None) -> str:
        """Read file content."""
        if not file_path:
            return "// Empty file"

        path = Path(file_path)
        if path.exists():
            try:
                return path.read_text()
            except Exception as e:
                logger.warning("Failed to read file", path=file_path, error=str(e))

        # Return placeholder for non-existent files
        return f"// Placeholder for {file_path}\n// Original content not available"

    def _extract_code(self, content: str | None) -> str:
        """Extract code from LLM response."""
        # Handle None content
        if not content:
            return "// No content generated"
        
        # Try to find code blocks
        if "```" in content:
            blocks = content.split("```")
            for i, block in enumerate(blocks):
                if i % 2 == 1:  # Odd indices are code blocks
                    # Remove language identifier if present
                    lines = block.split("\n")
                    if lines and not lines[0].strip().startswith("//"):
                        lines = lines[1:]
                    return "\n".join(lines).strip()

        # Return as-is if no code blocks
        return content.strip()

    async def _quick_verify(self, change: PLCChange) -> bool:
        """
        Quick syntax/compilation check.
        Part of inner verification loop (Spotify Part 3).
        """
        # Basic syntax checks
        if not change.new_code.strip():
            return False

        # Check for obviously broken syntax
        if change.new_code.count("(") != change.new_code.count(")"):
            return False

        # Could add more checks here
        return True

    async def _attempt_fix(
        self, change: PLCChange, llm: BaseLLMProvider, ctx: AgentContext
    ) -> None:
        """
        Try to fix a failed change.
        Agent uses verification feedback to improve.
        """
        fix_prompt = f"""The following code change failed verification:

## Original Code
```
{change.old_code}
```

## Modified Code (has issues)
```
{change.new_code}
```

## Task
{change.reason}

Please fix the issues and provide corrected code."""

        try:
            response = await llm.generate(
                messages=[Message(role=MessageRole.USER, content=fix_prompt)],
                max_tokens=2000,
            )

            fixed_code = self._extract_code(response.content)
            change.new_code = fixed_code
            ctx.turns_taken += 1

            logger.info("Applied fix attempt")

        except Exception as e:
            logger.warning("Fix attempt failed", error=str(e))

    async def _final_verification(self) -> bool:
        """Run final verification on all changes."""
        if not self.changes:
            return True

        from background_coding_agents.verifiers.plc_compiler_verifier import (
            PLCCompilerVerifier,
        )
        from background_coding_agents.verifiers.safety_verifier import SafetyVerifier

        results = []

        # Compiler verification
        try:
            compiler = PLCCompilerVerifier()
            compile_result = await compiler.verify(
                {"changes": [c.model_dump() for c in self.changes]},
                self.site_config.model_dump(),
            )
            results.append(compile_result)
        except Exception as e:
            logger.error("Compiler verification failed", error=str(e))
            results.append({"passed": False, "error": str(e)})

        # Safety verification
        try:
            safety = SafetyVerifier()
            safety_result = await safety.verify(
                {"changes": [c.model_dump() for c in self.changes]},
                self.site_config.model_dump(),
            )
            results.append(safety_result)

            if not safety_result.get("passed", True):
                self._audit_logger.log_safety_violation(
                    site_name=self.site_config.name,
                    violation_type="verification_failure",
                    file_path="multiple",
                    details=safety_result.get("message", "Unknown safety issue"),
                )
        except Exception as e:
            logger.error("Safety verification failed", error=str(e))
            results.append({"passed": False, "error": str(e)})

        if self.result:
            self.result.verification_results = results

        return all(r.get("passed", False) for r in results)

    async def close(self) -> None:
        """Close resources."""
        if self._llm_provider:
            await self._llm_provider.close()
            self._llm_provider = None


class MCPTools:
    """
    Model Context Protocol tools for the agent.

    Spotify Lesson (Part 2):
    - Keep tools limited and focused
    - More tools = more unpredictability
    - Custom tools are better than generic ones
    """

    @staticmethod
    async def verify(code: str, site_config: dict) -> dict:
        """
        Verification tool exposed to agent.

        Agent doesn't know implementation details,
        just knows it can verify changes.
        """
        from background_coding_agents.verifiers.plc_compiler_verifier import (
            PLCCompilerVerifier,
        )

        verifier = PLCCompilerVerifier()
        return await verifier.verify({"code": code}, site_config)

    @staticmethod
    async def git_diff() -> str:
        """Limited git access - no push, only diff."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout or "No staged changes"
        except Exception as e:
            return f"Error getting diff: {e}"

    @staticmethod
    async def ripgrep(pattern: str, path: str) -> list[str]:
        """Search for patterns in code."""
        import subprocess

        try:
            result = subprocess.run(
                ["rg", "-l", pattern, path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout.strip().split("\n") if result.stdout else []
        except Exception:
            return []


# Export for backward compatibility
__all__ = ["PLCAgent", "PLCChange", "MCPTools", "AgentContext"]
