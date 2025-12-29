"""
PLC code change models.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class ChangeStatus(str, Enum):
    """Status of a change request."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYED = "deployed"
    ROLLBACK = "rollback"


class PLCChange(BaseModel):
    """
    Represents a single change to PLC code.

    Tracks before/after state for auditing and rollback.
    """

    file_path: str = Field(..., description="Path to the modified file")
    old_code: str = Field(..., description="Original code content")
    new_code: str = Field(..., description="Modified code content")
    reason: str = Field(..., description="Explanation of why the change was made")

    # Location within file
    start_line: int | None = Field(default=None, description="Starting line number", ge=1)
    end_line: int | None = Field(default=None, description="Ending line number", ge=1)

    # Metadata
    change_type: str = Field(
        default="modification",
        description="Type of change (modification, addition, deletion)",
    )
    agent_turn: int = Field(
        default=0, description="Agent turn number when change was made", ge=0
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Safety classification
    affects_safety: bool = Field(
        default=False, description="Whether change affects safety-critical code"
    )
    requires_certification: bool = Field(
        default=False, description="Whether change requires re-certification"
    )

    @computed_field
    @property
    def lines_added(self) -> int:
        """Count of lines added."""
        old_lines = len(self.old_code.splitlines())
        new_lines = len(self.new_code.splitlines())
        return max(0, new_lines - old_lines)

    @computed_field
    @property
    def lines_removed(self) -> int:
        """Count of lines removed."""
        old_lines = len(self.old_code.splitlines())
        new_lines = len(self.new_code.splitlines())
        return max(0, old_lines - new_lines)

    def to_diff(self) -> str:
        """Generate a unified diff representation."""
        import difflib

        old_lines = self.old_code.splitlines(keepends=True)
        new_lines = self.new_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm="",
        )
        return "".join(diff)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "file_path": "src/safety_interlocks.st",
                    "old_code": "IF Guard_Sensor = TRUE THEN",
                    "new_code": "SAFETY_GUARD_MONITOR(Guard1, Guard2, TestPulse => Safety_OK);",
                    "reason": "Update to redundant guard monitoring per ISO 13849-1:2023",
                }
            ]
        }
    }


class ChangeRequest(BaseModel):
    """
    Change Authorization Request (CAR) for manufacturing.

    Similar to a Pull Request in software development,
    but with additional safety and compliance requirements.
    """

    car_id: str = Field(..., description="Unique Change Authorization Request ID")
    site_name: str = Field(..., description="Target manufacturing site")
    migration_name: str = Field(..., description="Associated migration")
    status: ChangeStatus = Field(default=ChangeStatus.DRAFT)

    # Changes included
    changes: list[PLCChange] = Field(default_factory=list)

    # Summary
    title: str = Field(..., description="Brief title of the change")
    description: str = Field(default="", description="Detailed description")
    risk_assessment: str = Field(
        default="", description="Risk assessment for the change"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: datetime | None = None
    deployed_at: datetime | None = None

    # Review information
    requested_by: str | None = Field(default=None, description="User who requested the change")
    reviewed_by: str | None = Field(default=None, description="User who reviewed the change")
    review_notes: str | None = None

    # Safety review (manufacturing-specific)
    safety_review_required: bool = Field(default=True)
    safety_review_passed: bool = Field(default=False)
    safety_reviewer: str | None = None
    safety_review_notes: str | None = None

    # Verification results
    verification_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results from all verification steps",
    )

    # Rollback information
    rollback_plan: str = Field(
        default="", description="Plan for rolling back changes if issues arise"
    )
    backup_created: bool = Field(default=False)
    backup_path: str | None = None

    @computed_field
    @property
    def total_changes(self) -> int:
        """Total number of changes in this request."""
        return len(self.changes)

    @computed_field
    @property
    def files_affected(self) -> list[str]:
        """List of unique files affected by changes."""
        return list(set(c.file_path for c in self.changes))

    @computed_field
    @property
    def has_safety_impact(self) -> bool:
        """Check if any change affects safety-critical code."""
        return any(c.affects_safety for c in self.changes)

    def approve(self, reviewer: str, notes: str = "") -> None:
        """Approve the change request."""
        self.status = ChangeStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        self.updated_at = datetime.utcnow()

    def reject(self, reviewer: str, notes: str) -> None:
        """Reject the change request."""
        self.status = ChangeStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = datetime.utcnow()
        self.review_notes = notes
        self.updated_at = datetime.utcnow()

    def mark_deployed(self) -> None:
        """Mark the change as deployed."""
        self.status = ChangeStatus.DEPLOYED
        self.deployed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"CAR ID: {self.car_id}",
            f"Site: {self.site_name}",
            f"Status: {self.status.value}",
            f"Title: {self.title}",
            f"Files affected: {len(self.files_affected)}",
            f"Total changes: {self.total_changes}",
            f"Safety impact: {'Yes' if self.has_safety_impact else 'No'}",
        ]
        return "\n".join(lines)
