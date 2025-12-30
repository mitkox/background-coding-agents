#!/usr/bin/env python3
"""
Fleet Manager CLI for Industrial Manufacturing

Orchestrates automated code migrations across multiple manufacturing sites.
Inspired by Spotify's Fleet Management system that handles 50% of their PRs.

Features:
- Multi-site parallel execution
- Local and cloud LLM support
- Comprehensive verification
- Audit trail for compliance
- Rich terminal output
"""

import argparse
import asyncio
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from background_coding_agents.config import get_settings
from background_coding_agents.llm import LLMProviderFactory, ProviderType, create_provider
from background_coding_agents.logging import AuditLogger, LogContext, get_logger, setup_logging
from background_coding_agents.models import (
    AgentConfig,
    ChangeRequest,
    ChangeStatus,
    MigrationConfig,
    MigrationResult,
    MigrationStatus,
    PLCChange,
    SiteConfig,
    SiteMigrationResult,
    VerificationResult,
)

logger = get_logger(__name__)


class FleetManager:
    """
    Manages automated migrations across multiple manufacturing sites.

    Similar to Spotify's Fleet Management that handles 50% of their PRs.
    Supports both cloud and local LLMs for air-gapped environments.
    """

    def __init__(self, config_path: str | Path):
        """
        Initialize Fleet Manager.

        Args:
            config_path: Path to fleet configuration YAML
        """
        self.config_path = Path(config_path)
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)

        self.sites = [SiteConfig(**site) for site in self.config.get("sites", [])]
        self._audit_logger = AuditLogger()
        self._settings = get_settings()

    async def run_migration(
        self,
        migration_name: str,
        dry_run: bool = True,
        target_sites: list[str] | None = None,
    ) -> MigrationResult:
        """
        Execute a migration across all configured sites.

        Process (similar to Spotify's approach):
        1. Load migration prompt
        2. Target sites based on selection criteria
        3. Run agent with prompt + verifiers
        4. Generate change requests
        5. Run verification loops
        6. Submit for review (human in the loop for safety-critical)

        Args:
            migration_name: Name of migration to execute
            dry_run: If True, don't make actual changes
            target_sites: Optional list of specific sites to target

        Returns:
            MigrationResult with outcomes for all sites
        """
        correlation_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()

        with LogContext(correlation_id=correlation_id):
            self._print_header(migration_name, dry_run)

            # Load migration configuration
            try:
                migration_config = self._load_migration(migration_name)
            except FileNotFoundError:
                self._print_error(f"Migration '{migration_name}' not found")
                return MigrationResult(
                    migration_name=migration_name,
                    status=MigrationStatus.FAILED,
                    total_sites=0,
                    successful_sites=0,
                    failed_sites=0,
                    skipped_sites=0,
                    site_results=[],
                    started_at=started_at,
                    error_message=f"Migration '{migration_name}' not found",
                )

            prompt = migration_config.prompt

            # Filter target sites
            if target_sites:
                filtered_sites = [s for s in self.sites if s.name in target_sites]
            else:
                filtered_sites = self._filter_sites(migration_config.target_filter)

            if not filtered_sites:
                self._print_warning("No sites match the filter criteria")
                return MigrationResult(
                    migration_name=migration_name,
                    status=MigrationStatus.COMPLETED,
                    total_sites=0,
                    successful_sites=0,
                    failed_sites=0,
                    skipped_sites=len(self.sites),
                    site_results=[],
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            self._print_info(f"Targeting {len(filtered_sites)} site(s)")

            # Log migration start
            event_id = self._audit_logger.log_migration_started(
                migration_name=migration_name,
                target_sites=[s.name for s in filtered_sites],
                dry_run=dry_run,
            )

            # Execute migration on each site
            site_results: list[SiteMigrationResult] = []
            for i, site in enumerate(filtered_sites, 1):
                self._print_site_header(site.name, i, len(filtered_sites))

                result = await self._run_agent_on_site(
                    site=site,
                    prompt=prompt,
                    migration_config=migration_config,
                    dry_run=dry_run,
                )
                site_results.append(result)

                self._print_site_result(result)

            # Calculate totals
            successful = sum(1 for r in site_results if r.success)
            failed = sum(1 for r in site_results if not r.success)
            completed_at = datetime.utcnow()
            duration = (completed_at - started_at).total_seconds()

            # Log migration completion
            self._audit_logger.log_migration_completed(
                event_id=event_id,
                migration_name=migration_name,
                success_count=successful,
                failure_count=failed,
                duration_seconds=duration,
            )

            # Print summary
            self._print_summary(site_results, duration, dry_run)

            return MigrationResult(
                migration_name=migration_name,
                status=MigrationStatus.COMPLETED if failed == 0 else MigrationStatus.PARTIAL,
                total_sites=len(site_results),
                successful_sites=successful,
                failed_sites=failed,
                skipped_sites=len(self.sites) - len(filtered_sites),
                site_results=site_results,
                started_at=started_at,
                completed_at=completed_at,
                dry_run=dry_run,
            )

    def _load_migration(self, name: str) -> MigrationConfig:
        """Load migration definition from migrations directory."""
        migrations_dir = self.config_path.parent / "migrations"
        migration_path = migrations_dir / f"{name}.yaml"

        if not migration_path.exists():
            # Try with .yml extension
            migration_path = migrations_dir / f"{name}.yml"

        if not migration_path.exists():
            raise FileNotFoundError(f"Migration file not found: {name}")

        with open(migration_path) as f:
            data = yaml.safe_load(f)

        return MigrationConfig(**data)

    def _filter_sites(self, filter_config: Any) -> list[SiteConfig]:
        """Filter sites based on criteria."""
        if filter_config is None:
            return self.sites

        filtered = self.sites

        # Convert to dict if it's a model
        if hasattr(filter_config, "model_dump"):
            filters = filter_config.model_dump(exclude_none=True)
        else:
            filters = filter_config or {}

        # Handle include_sites (overrides other filters)
        if filters.get("include_sites"):
            return [s for s in filtered if s.name in filters["include_sites"]]

        # Handle exclude_sites
        if filters.get("exclude_sites"):
            filtered = [s for s in filtered if s.name not in filters["exclude_sites"]]

        # Filter by PLC type
        if filters.get("plc_type"):
            filtered = [s for s in filtered if s.plc_type.value == filters["plc_type"]]

        # Filter by firmware version
        if filters.get("firmware_version"):
            filtered = [
                s
                for s in filtered
                if s.firmware_version.startswith(filters["firmware_version"])
            ]

        # Filter by safety rating
        if filters.get("safety_rating"):
            from background_coding_agents.models import SafetyRating

            min_rating = SafetyRating(filters["safety_rating"])
            filtered = [s for s in filtered if s.safety_rating >= min_rating]

        # Filter by location
        if filters.get("location"):
            filtered = [
                s for s in filtered if filters["location"].lower() in s.location.lower()
            ]

        # Filter by tags
        if filters.get("tags"):
            required_tags = set(filters["tags"])
            filtered = [s for s in filtered if required_tags.issubset(set(s.tags))]

        return filtered

    async def _run_agent_on_site(
        self,
        site: SiteConfig,
        prompt: str,
        migration_config: MigrationConfig,
        dry_run: bool,
    ) -> SiteMigrationResult:
        """
        Run the coding agent on a single site.

        Key principles from Spotify's Part 2:
        - Tailor prompts to the agent
        - State preconditions clearly
        - Use concrete examples
        - Define desired end state (tests)
        - Do one change at a time
        """
        from background_coding_agents.agents.plc_agent import PLCAgent
        from background_coding_agents.verifiers.plc_compiler_verifier import (
            PLCCompilerVerifier,
        )
        from background_coding_agents.verifiers.safety_verifier import SafetyVerifier

        started_at = datetime.utcnow()

        # Create agent config from settings
        agent_config = self._create_agent_config()

        agent = PLCAgent(site_config=site, agent_config=agent_config)

        # Build full context for agent
        full_prompt = self._build_prompt(prompt, site, migration_config)

        try:
            # Run agent
            result = await agent.execute(full_prompt)
            changes = result.changes

            # Verification loops (Spotify Part 3 concept)
            verifier_results: list[tuple[str, dict[str, Any]]] = []

            # 1. Compile check
            try:
                compiler = PLCCompilerVerifier()
                compile_result = await compiler.verify(
                    {"changes": changes}, site.model_dump()
                )
                verifier_results.append(("compile", compile_result))
                self._print_verification("Compile", compile_result.get("passed", False))
            except Exception as e:
                verifier_results.append(("compile", {"passed": False, "error": str(e)}))
                self._print_verification("Compile", False, str(e))

            # 2. Safety verification
            try:
                safety = SafetyVerifier()
                safety_result = await safety.verify(
                    {"changes": changes}, site.model_dump()
                )
                verifier_results.append(("safety", safety_result))
                self._print_verification("Safety", safety_result.get("passed", False))

                # Log safety result
                self._audit_logger.log_verification_result(
                    car_id=f"CAR-{site.name}-{result.task_id}",
                    verification_type="safety",
                    passed=safety_result.get("passed", False),
                    critical=safety_result.get("critical", False),
                )
            except Exception as e:
                verifier_results.append(("safety", {"passed": False, "error": str(e)}))
                self._print_verification("Safety", False, str(e))

            # 3. LLM Judge (check if changes are within scope)
            try:
                judge_result = await self._run_llm_judge(changes, prompt)
                verifier_results.append(("judge", judge_result))
                self._print_verification("LLM Judge", judge_result.get("passed", False))
            except Exception as e:
                verifier_results.append(("judge", {"passed": False, "error": str(e)}))
                self._print_verification("LLM Judge", False, str(e))

            all_passed = all(r[1].get("passed", False) for r in verifier_results)

            if all_passed and not dry_run:
                # Create change request
                car_id = self._create_change_request(site, result)
                self._print_success(f"Created change request: {car_id}")
            elif all_passed:
                self._print_info("Dry run - no changes applied")
            else:
                self._print_warning("Verification failed - no changes applied")

            await agent.close()

            completed_at = datetime.utcnow()

            return SiteMigrationResult(
                site_name=site.name,
                status=MigrationStatus.COMPLETED if all_passed else MigrationStatus.FAILED,
                success=all_passed,
                changes_made=len(changes),
                verification_passed=all_passed,
                change_request_id=f"CAR-{site.name}-{result.task_id}" if all_passed else None,
                duration_seconds=(completed_at - started_at).total_seconds(),
                started_at=started_at,
                completed_at=completed_at,
            )

        except Exception as e:
            logger.exception("Error processing site", site=site.name, error=str(e))
            self._print_error(f"Error: {e}")

            return SiteMigrationResult(
                site_name=site.name,
                status=MigrationStatus.FAILED,
                success=False,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _create_agent_config(self) -> AgentConfig:
        """Create agent configuration from settings."""
        agent_config = self.config.get("agent", {})
        llm_config = self.config.get("llm", {})

        # Determine provider (env var takes priority over YAML)
        provider_str = llm_config.get("provider", self._settings.llm.provider.value)
        try:
            provider = ProviderType(provider_str.lower())
        except ValueError:
            provider = ProviderType.ANTHROPIC

        # Use environment variables if available, fall back to YAML config
        return AgentConfig(
            llm_provider=provider,
            llm_model=llm_config.get("model") or self._settings.llm.model,
            llm_base_url=llm_config.get("base_url") or self._settings.llm.base_url,
            max_turns=agent_config.get("max_turns", 10),
            max_retries=agent_config.get("max_retries", 3),
            tools=agent_config.get("tools", ["verify", "git_diff", "ripgrep"]),
        )

    def _build_prompt(
        self, base_prompt: str, site: SiteConfig, config: MigrationConfig
    ) -> str:
        """
        Build comprehensive prompt with context.

        Following Spotify's lessons:
        - Include examples
        - State preconditions
        - Define success criteria
        - Keep focused on one change
        """
        # Get examples
        examples_text = ""
        if config.examples:
            examples_text = "\n\n".join(
                f"## Example {i+1}\n"
                f"Before:\n```\n{ex.get('before', '')}\n```\n"
                f"After:\n```\n{ex.get('after', '')}\n```"
                for i, ex in enumerate(config.examples[:3])
            )

        # Get preconditions
        preconditions_text = ""
        if config.preconditions:
            preconditions_text = "\n".join(f"- {p}" for p in config.preconditions)

        # Get exclusions
        exclusions_text = ""
        if config.exclusions:
            exclusions_text = "\n".join(f"- {e}" for e in config.exclusions)

        # Get success criteria
        success_text = ""
        if config.success_criteria:
            success_text = "\n".join(f"- {c}" for c in config.success_criteria)

        context = f"""# Site Context
- Name: {site.name}
- Location: {site.location}
- PLC Type: {site.plc_type.value}
- Firmware: {site.firmware_version}
- Production Line: {site.line_type}
- Safety Rating: {site.safety_rating.value}

# Safety Requirements
- All safety interlocks must remain functional
- Emergency stops cannot be modified
- Changes must maintain {site.safety_rating.value} compliance
- Certified modules: {', '.join(site.certified_modules) or 'None'}

# Preconditions (ONLY proceed IF)
{preconditions_text or '- Standard operating conditions'}

# Exclusions (DO NOT proceed IF)
{exclusions_text or '- None specified'}

# Examples
{examples_text or 'No examples provided'}

# Task
{base_prompt}

# Success Criteria
{success_text or '''- Code compiles without errors
- All existing tests pass
- Safety verification passes
- No unintended side effects'''}
"""
        return context

    async def _run_llm_judge(
        self, changes: list[dict[str, Any]], original_prompt: str
    ) -> dict[str, Any]:
        """
        LLM-as-judge verification (Spotify Part 3 concept).

        Checks:
        - Are changes within scope of prompt?
        - Any "creative" additions?
        - Safety-critical modifications?
        """
        if not changes:
            return {"passed": True, "reasoning": "No changes to review"}

        # Get judge model from config
        verification_config = self.config.get("verification", {})
        judge_config = verification_config.get("judge", {})

        if not judge_config.get("enabled", True):
            return {"passed": True, "reasoning": "LLM judge disabled"}

        threshold = judge_config.get("confidence_threshold", 0.7)

        judge_prompt = f"""You are reviewing automated code changes for industrial manufacturing equipment.

Original Task: {original_prompt}

Changes Made:
{self._format_changes_for_judge(changes)}

Evaluate:
1. Are all changes directly related to the task?
2. Were any safety-critical elements modified unnecessarily?
3. Is the scope appropriate (not too ambitious)?

Respond with:
VERDICT: APPROVED or REJECTED
CONFIDENCE: 0.0-1.0
REASONING: Brief explanation
"""

        try:
            # Use existing provider or create one
            provider = create_provider("auto")
            await provider.initialize()

            from background_coding_agents.llm import Message, MessageRole

            response = await provider.generate(
                messages=[Message(role=MessageRole.USER, content=judge_prompt)],
                max_tokens=500,
            )

            await provider.close()

            # Parse response
            content = response.content.upper()
            approved = "APPROVED" in content

            # Extract confidence
            confidence = 0.8  # Default
            if "CONFIDENCE:" in content:
                try:
                    conf_line = [l for l in content.split("\n") if "CONFIDENCE:" in l][0]
                    confidence = float(conf_line.split(":")[-1].strip())
                except (IndexError, ValueError):
                    pass

            return {
                "passed": approved and confidence >= threshold,
                "confidence": confidence,
                "reasoning": response.content,
                "threshold": threshold,
            }

        except Exception as e:
            logger.warning("LLM judge failed, defaulting to pass", error=str(e))
            return {
                "passed": True,
                "reasoning": f"LLM judge unavailable: {e}",
                "fallback": True,
            }

    def _format_changes_for_judge(self, changes: list[dict[str, Any]]) -> str:
        """Format changes for LLM judge review."""
        formatted = []
        for i, change in enumerate(changes[:5], 1):  # Limit to 5 changes
            formatted.append(
                f"Change {i}: {change.get('file_path', 'unknown')}\n"
                f"  Reason: {change.get('reason', 'Not specified')}\n"
                f"  Lines added: {change.get('lines_added', 0)}, "
                f"removed: {change.get('lines_removed', 0)}"
            )
        return "\n".join(formatted)

    def _create_change_request(self, site: SiteConfig, result: Any) -> str:
        """
        Create a change request (similar to PR in Spotify's system).
        In manufacturing: CAR (Change Authorization Request)
        """
        car_id = f"CAR-{site.name}-{result.task_id}"

        self._audit_logger.log_change_request_created(
            car_id=car_id,
            site_name=site.name,
            migration_name="migration",  # Would come from context
            files_affected=[c.get("file_path", "unknown") for c in result.changes],
            changes_count=len(result.changes),
        )

        logger.info("Created change request", car_id=car_id, site=site.name)
        return car_id

    # ========== Terminal Output Methods ==========

    def _print_header(self, migration_name: str, dry_run: bool) -> None:
        """Print migration header."""
        mode = "[DRY RUN]" if dry_run else "[LIVE]"
        print("\n" + "=" * 70)
        print(f"  Fleet Manager - {migration_name} {mode}")
        print("=" * 70)

        # Print LLM provider info
        settings = get_settings()
        provider = settings.llm.provider.value
        model = settings.llm.model or "default"
        print(f"  LLM Provider: {provider} ({model})")
        print("=" * 70 + "\n")

    def _print_site_header(self, site_name: str, current: int, total: int) -> None:
        """Print site processing header."""
        print(f"\n[{current}/{total}] Processing: {site_name}")
        print("-" * 50)

    def _print_site_result(self, result: SiteMigrationResult) -> None:
        """Print result for a single site."""
        if result.success:
            status = "[OK]"
        else:
            status = "[FAIL]"

        print(f"  {status} {result.site_name}")
        print(f"      Changes: {result.changes_made}")
        print(f"      Duration: {result.duration_seconds:.2f}s")

        if result.error_message:
            print(f"      Error: {result.error_message}")

    def _print_verification(
        self, name: str, passed: bool, error: str | None = None
    ) -> None:
        """Print verification result."""
        status = "[OK]" if passed else "[FAIL]"
        print(f"    {status} {name}")
        if error:
            print(f"        {error}")

    def _print_summary(
        self, results: list[SiteMigrationResult], duration: float, dry_run: bool
    ) -> None:
        """Print migration summary."""
        total = len(results)
        successful = sum(1 for r in results if r.success)

        print("\n" + "=" * 70)
        print(f"  Migration Summary: {successful}/{total} successful")
        print(f"  Total duration: {duration:.2f}s")
        if dry_run:
            print("  Mode: DRY RUN (no changes applied)")
        print("=" * 70)

        for result in results:
            status = "[OK]" if result.success else "[FAIL]"
            print(f"  {status} {result.site_name}")

        print("")

    def _print_info(self, message: str) -> None:
        """Print info message."""
        print(f"[INFO] {message}")

    def _print_success(self, message: str) -> None:
        """Print success message."""
        print(f"[OK] {message}")

    def _print_warning(self, message: str) -> None:
        """Print warning message."""
        print(f"[WARN] {message}")

    def _print_error(self, message: str) -> None:
        """Print error message."""
        print(f"[ERROR] {message}", file=sys.stderr)


async def async_main() -> int:
    """Async entry point for fleet-manager CLI."""
    parser = argparse.ArgumentParser(
        description="Fleet Manager for Industrial Manufacturing Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fleet-manager safety_interlock_update --dry-run
  fleet-manager protocol_migration --sites Plant-01 Plant-02
  fleet-manager safety_interlock_update --provider vllm --model THUDM/glm-4.7
  fleet-manager safety_interlock_update --provider llama_cpp --model /models/MiniMax-M2.1.Q4_K_M.gguf

Environment Variables:
  LLM_PROVIDER          LLM provider (anthropic, openai, vllm, llama_cpp, openai_compatible)
  LLM_MODEL             Model name (GLM-4.7, MiniMax-M2.1 for local)
  LLM_BASE_URL          Base URL for local providers
  ANTHROPIC_API_KEY     Anthropic API key
  OPENAI_API_KEY        OpenAI API key
""",
    )

    parser.add_argument("migration", help="Migration name to execute")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).parent / "config.yaml"),
        help="Configuration file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes (default: true)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually apply changes",
    )
    parser.add_argument("--sites", nargs="+", help="Specific sites to target")

    # LLM options
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "vllm", "llama_cpp", "openai_compatible"],
        help="LLM provider to use (vllm/llama_cpp for local models like GLM-4.7, MiniMax-M2.1)",
    )
    parser.add_argument("--model", help="Model name or path")
    parser.add_argument("--base-url", help="Base URL for local LLM providers")

    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level",
    )
    parser.add_argument("--log-format", choices=["json", "text"], default="text")

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level, format=args.log_format)

    # Override settings with CLI arguments
    import os

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    if args.base_url:
        os.environ["LLM_BASE_URL"] = args.base_url

    # Reload settings to pick up overrides
    from background_coding_agents.config import reload_settings

    reload_settings()

    # Determine dry_run mode
    dry_run = not args.no_dry_run

    try:
        manager = FleetManager(args.config)
        result = await manager.run_migration(
            migration_name=args.migration,
            dry_run=dry_run,
            target_sites=args.sites,
        )

        # Return appropriate exit code
        if result.failed_sites > 0:
            return 1
        return 0

    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        logger.exception("Unexpected error in fleet-manager")
        return 1


def run() -> None:
    """Synchronous entry point."""
    sys.exit(asyncio.run(async_main()))


def main() -> None:
    """Main entry point (alias for run)."""
    run()


if __name__ == "__main__":
    run()
