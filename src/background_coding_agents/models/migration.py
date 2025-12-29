"""
Migration configuration and result models.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MigrationStatus(str, Enum):
    """Migration execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    ROLLBACK = "rollback"


class TargetFilter(BaseModel):
    """
    Filter criteria for selecting target sites.

    All criteria are AND-combined (site must match all specified filters).
    """

    plc_type: str | None = Field(default=None, description="Filter by PLC type")
    firmware_version: str | None = Field(
        default=None, description="Filter by firmware version prefix"
    )
    safety_rating: str | None = Field(
        default=None, description="Minimum safety rating (e.g., 'SIL-2')"
    )
    location: str | None = Field(
        default=None, description="Filter by location (partial match)"
    )
    line_type: str | None = Field(default=None, description="Filter by production line type")
    tags: list[str] = Field(
        default_factory=list, description="Required tags (all must be present)"
    )
    exclude_sites: list[str] = Field(
        default_factory=list, description="Site names to exclude"
    )
    include_sites: list[str] = Field(
        default_factory=list, description="Only include these sites (overrides other filters)"
    )


class MigrationConfig(BaseModel):
    """
    Configuration for a fleet-wide migration.

    Follows Spotify's migration prompt structure with context engineering.
    """

    name: str = Field(..., description="Unique migration identifier", min_length=1)
    description: str = Field(..., description="Human-readable description of the migration")
    version: str = Field(default="1.0.0", description="Migration version")

    # Main prompt content
    prompt: str = Field(..., description="Natural language task description for the agent")

    # Context engineering (Spotify Part 2)
    preconditions: list[str] = Field(
        default_factory=list,
        description="ONLY IF conditions - when this migration should apply",
    )
    exclusions: list[str] = Field(
        default_factory=list,
        description="DO NOT IF conditions - when to skip",
    )

    # Examples (3-5 variations recommended)
    examples: list[dict[str, str]] = Field(
        default_factory=list,
        description="Before/after code examples",
    )

    # Success criteria (measurable checkpoints)
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria for successful completion",
    )

    # Target site selection
    target_filter: TargetFilter = Field(
        default_factory=TargetFilter,
        description="Filter for selecting target sites",
    )

    # Safety constraints
    forbidden_modifications: list[str] = Field(
        default_factory=list,
        description="Files/patterns that must NOT be modified",
    )
    required_verifications: list[str] = Field(
        default_factory=lambda: ["compile", "safety"],
        description="Required verification steps",
    )
    requires_human_review: bool = Field(
        default=True, description="Whether changes require human review"
    )

    # Execution settings
    dry_run: bool = Field(
        default=True, description="Run without making actual changes"
    )
    max_concurrent_sites: int = Field(
        default=5, description="Maximum sites to process in parallel", ge=1
    )
    continue_on_failure: bool = Field(
        default=False, description="Continue processing other sites if one fails"
    )
    rollback_on_failure: bool = Field(
        default=True, description="Rollback changes on verification failure"
    )

    # Metadata
    author: str | None = Field(default=None, description="Migration author")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    tags: list[str] = Field(default_factory=list, description="Migration tags")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_prompt_context(self) -> str:
        """Generate full context string for agent prompt."""
        sections = []

        if self.preconditions:
            sections.append("# Preconditions (ONLY IF)")
            for cond in self.preconditions:
                sections.append(f"- {cond}")
            sections.append("")

        if self.exclusions:
            sections.append("# Exclusions (DO NOT IF)")
            for exc in self.exclusions:
                sections.append(f"- {exc}")
            sections.append("")

        if self.examples:
            sections.append("# Examples")
            for i, ex in enumerate(self.examples, 1):
                sections.append(f"## Example {i}")
                if "before" in ex:
                    sections.append(f"Before:\n```\n{ex['before']}\n```")
                if "after" in ex:
                    sections.append(f"After:\n```\n{ex['after']}\n```")
                if "explanation" in ex:
                    sections.append(f"Explanation: {ex['explanation']}")
                sections.append("")

        sections.append("# Task")
        sections.append(self.prompt)
        sections.append("")

        if self.forbidden_modifications:
            sections.append("# DO NOT Modify")
            for forbidden in self.forbidden_modifications:
                sections.append(f"- {forbidden}")
            sections.append("")

        if self.success_criteria:
            sections.append("# Success Criteria")
            for criterion in self.success_criteria:
                sections.append(f"- {criterion}")

        return "\n".join(sections)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "safety_interlock_update",
                    "description": "Update safety interlock logic to ISO 13849-1:2023",
                    "prompt": "Update safety interlock patterns to use redundant monitoring",
                    "preconditions": [
                        "Site has SIL-2 or higher rating",
                        "Firmware version 2.9+",
                    ],
                    "success_criteria": [
                        "All safety interlocks use redundant inputs",
                        "Diagnostic coverage meets PLd requirements",
                    ],
                }
            ]
        }
    }


class SiteMigrationResult(BaseModel):
    """Result of migration for a single site."""

    site_name: str
    status: MigrationStatus
    success: bool
    changes_made: int = 0
    verification_passed: bool = False
    error_message: str | None = None
    change_request_id: str | None = None
    duration_seconds: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MigrationResult(BaseModel):
    """
    Complete result of a fleet-wide migration.
    """

    migration_name: str
    status: MigrationStatus
    total_sites: int
    successful_sites: int
    failed_sites: int
    skipped_sites: int
    site_results: list[SiteMigrationResult]
    started_at: datetime
    completed_at: datetime | None = None
    dry_run: bool = True
    error_message: str | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_sites == 0:
            return 0.0
        return (self.successful_sites / self.total_sites) * 100

    @property
    def duration_seconds(self) -> float | None:
        """Calculate total migration duration."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Migration: {self.migration_name}",
            f"Status: {self.status.value}",
            f"Results: {self.successful_sites}/{self.total_sites} successful ({self.success_rate:.1f}%)",
            "",
            "Site Results:",
        ]
        for result in self.site_results:
            status_icon = "OK" if result.success else "FAIL"
            lines.append(f"  [{status_icon}] {result.site_name}")
            if result.error_message:
                lines.append(f"       Error: {result.error_message}")

        return "\n".join(lines)
