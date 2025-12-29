"""
Agent configuration and result models.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from background_coding_agents.llm.base import ProviderType


class AgentStatus(str, Enum):
    """Agent execution status."""

    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    """A single step in the agent's execution plan."""

    step_number: int = Field(..., ge=1)
    action: str = Field(..., description="Action to perform")
    target_file: str | None = Field(default=None, description="Target file for the action")
    description: str = Field(..., description="Human-readable description")
    status: str = Field(default="pending")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: str | None = None
    error: str | None = None


class ExecutionPlan(BaseModel):
    """
    Agent's execution plan for a task.

    Created during the planning phase before execution.
    """

    task_id: str = Field(..., description="Unique task identifier")
    prompt: str = Field(..., description="Original task prompt")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    steps: list[PlanStep] = Field(default_factory=list)

    # Files involved
    relevant_files: list[str] = Field(
        default_factory=list, description="Files relevant to the task"
    )
    files_to_modify: list[str] = Field(
        default_factory=list, description="Files that will be modified"
    )

    # Constraints
    max_turns: int = Field(default=10, ge=1)
    estimated_complexity: str = Field(
        default="medium", description="Estimated complexity (low, medium, high)"
    )

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def progress_percent(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100


class AgentConfig(BaseModel):
    """
    Configuration for a background coding agent.

    Controls agent behavior, LLM provider settings, and constraints.
    """

    # Agent identification
    agent_type: str = Field(default="plc_agent", description="Type of agent")
    agent_version: str = Field(default="1.0.0")

    # LLM provider configuration
    llm_provider: ProviderType = Field(
        default=ProviderType.ANTHROPIC, description="LLM provider to use"
    )
    llm_model: str | None = Field(
        default=None, description="Model name (uses provider default if not specified)"
    )
    llm_base_url: str | None = Field(
        default=None, description="Base URL for LLM API (for local providers)"
    )
    llm_api_key: str | None = Field(
        default=None, description="API key (reads from env if not specified)"
    )

    # LLM parameters
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)

    # Execution constraints
    max_turns: int = Field(
        default=10, description="Maximum turns before stopping", ge=1, le=100
    )
    max_retries: int = Field(
        default=3, description="Maximum retries on failure", ge=0, le=10
    )
    timeout_seconds: int = Field(
        default=300, description="Timeout for entire execution", ge=30
    )

    # Available tools
    tools: list[str] = Field(
        default_factory=lambda: ["verify", "git_diff", "ripgrep"],
        description="Tools available to the agent",
    )

    # Verification settings
    enable_quick_verify: bool = Field(
        default=True, description="Enable quick verification after each change"
    )
    verification_timeout: int = Field(
        default=60, description="Timeout for verification in seconds"
    )

    # Safety constraints (manufacturing-specific)
    allow_safety_modifications: bool = Field(
        default=False,
        description="Allow modifications to safety-critical code (requires approval)",
    )
    forbidden_patterns: list[str] = Field(
        default_factory=lambda: [
            "E_STOP",
            "EMERGENCY_STOP",
            "SAFETY_STOP",
            "FORCE",
            "DISABLE.*SAFETY",
        ],
        description="Patterns that trigger safety review",
    )

    # Logging and telemetry
    enable_telemetry: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    trace_llm_calls: bool = Field(
        default=True, description="Log all LLM API calls for auditing"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_type": "plc_agent",
                    "llm_provider": "vllm",
                    "llm_model": "THUDM/glm-4.7",
                    "max_turns": 10,
                    "tools": ["verify", "git_diff", "ripgrep"],
                },
                {
                    "agent_type": "plc_agent",
                    "llm_provider": "llama_cpp",
                    "llm_model": "/models/MiniMax-M2.1.Q4_K_M.gguf",
                    "max_turns": 10,
                    "tools": ["verify", "git_diff", "ripgrep"],
                },
            ]
        }
    }


class AgentResult(BaseModel):
    """
    Result of an agent execution.

    Comprehensive result with all changes, verification outcomes,
    and execution metadata.
    """

    task_id: str = Field(..., description="Unique task identifier")
    site_name: str = Field(..., description="Target site name")
    status: AgentStatus = Field(default=AgentStatus.IDLE)
    success: bool = Field(default=False)

    # Execution details
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    turns_taken: int = Field(default=0, ge=0)

    # Plan and changes
    plan: ExecutionPlan | None = None
    changes: list[dict[str, Any]] = Field(
        default_factory=list, description="List of changes made"
    )

    # Verification results
    verification_results: list[dict[str, Any]] = Field(
        default_factory=list, description="Results from verification steps"
    )
    all_verifications_passed: bool = Field(default=False)

    # LLM usage
    llm_provider: str | None = None
    llm_model: str | None = None
    total_input_tokens: int = Field(default=0, ge=0)
    total_output_tokens: int = Field(default=0, ge=0)

    # Error handling
    error_message: str | None = None
    error_traceback: str | None = None
    retry_count: int = Field(default=0, ge=0)

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate execution duration."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.total_input_tokens + self.total_output_tokens

    def complete(self, success: bool = True) -> None:
        """Mark execution as complete."""
        self.completed_at = datetime.utcnow()
        self.success = success
        self.status = AgentStatus.COMPLETED if success else AgentStatus.FAILED

    def fail(self, error_message: str, traceback: str | None = None) -> None:
        """Mark execution as failed."""
        self.completed_at = datetime.utcnow()
        self.success = False
        self.status = AgentStatus.FAILED
        self.error_message = error_message
        self.error_traceback = traceback

    def add_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Add token usage from an LLM call."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        status = "SUCCESS" if self.success else "FAILED"
        lines = [
            f"Task: {self.task_id}",
            f"Site: {self.site_name}",
            f"Status: {status}",
            f"Turns: {self.turns_taken}",
            f"Changes: {len(self.changes)}",
            f"Tokens: {self.total_tokens:,}",
        ]

        if self.duration_seconds:
            lines.append(f"Duration: {self.duration_seconds:.2f}s")

        if self.error_message:
            lines.append(f"Error: {self.error_message}")

        return "\n".join(lines)
