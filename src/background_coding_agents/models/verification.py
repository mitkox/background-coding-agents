"""
Verification result models for safety-critical industrial environments.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationType(str, Enum):
    """Types of verification checks."""

    COMPILE = "compile"
    SAFETY = "safety"
    SIMULATION = "simulation"
    LLM_JUDGE = "llm_judge"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    SYNTAX = "syntax"
    LINT = "lint"
    TYPE_CHECK = "type_check"
    CUSTOM = "custom"


class Severity(str, Enum):
    """Issue severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

    @property
    def blocks_deployment(self) -> bool:
        """Check if this severity blocks deployment."""
        return self in (Severity.ERROR, Severity.CRITICAL)


class SafetyIssue(BaseModel):
    """
    A safety-related issue found during verification.

    Safety issues in manufacturing are treated with zero tolerance.
    """

    issue_type: str = Field(..., description="Type of safety issue")
    severity: Severity = Field(default=Severity.ERROR)
    message: str = Field(..., description="Human-readable issue description")
    file_path: str | None = Field(default=None, description="File where issue was found")
    line_number: int | None = Field(default=None, description="Line number of issue", ge=1)
    code_snippet: str | None = Field(default=None, description="Relevant code snippet")

    # Safety classification
    iec_standard: str | None = Field(
        default=None, description="Relevant IEC standard (e.g., 'IEC 61508')"
    )
    safety_function: str | None = Field(
        default=None, description="Affected safety function"
    )
    requires_certification: bool = Field(
        default=False, description="Whether issue requires re-certification"
    )

    # Recommended action
    recommended_action: str | None = Field(
        default=None, description="Recommended remediation action"
    )

    def to_string(self) -> str:
        """Generate formatted string representation."""
        location = ""
        if self.file_path:
            location = f" at {self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"

        return f"[{self.severity.value.upper()}] {self.issue_type}{location}: {self.message}"


class VerificationResult(BaseModel):
    """
    Result of a verification check.

    Supports the multi-layer verification strategy:
    1. Compiler check (fast, deterministic)
    2. Safety verification (critical, never skip)
    3. Simulation testing (optional)
    4. LLM judge (scope validation)
    """

    verification_type: VerificationType
    passed: bool = Field(..., description="Whether verification passed")
    message: str = Field(default="", description="Summary message")

    # Detailed results
    issues: list[SafetyIssue] = Field(
        default_factory=list, description="Issues found during verification"
    )
    warnings: list[str] = Field(default_factory=list, description="Non-blocking warnings")
    errors: list[str] = Field(default_factory=list, description="Blocking errors")

    # Critical flag for safety verification
    critical: bool = Field(
        default=False,
        description="If True, failure means hard stop (no retry, no skip)",
    )

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, description="Verification duration in ms")

    # Additional context
    details: dict[str, Any] = Field(default_factory=dict)
    raw_output: str | None = Field(default=None, description="Raw verification output")

    # For LLM judge
    confidence: float | None = Field(
        default=None, description="LLM judge confidence score (0-1)", ge=0.0, le=1.0
    )
    reasoning: str | None = Field(default=None, description="LLM judge reasoning")

    @property
    def has_critical_issues(self) -> bool:
        """Check if any issues are critical severity."""
        return any(issue.severity == Severity.CRITICAL for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0 or any(
            issue.severity in (Severity.ERROR, Severity.CRITICAL) for issue in self.issues
        )

    @property
    def error_count(self) -> int:
        """Count of errors."""
        return len(self.errors) + sum(
            1
            for issue in self.issues
            if issue.severity in (Severity.ERROR, Severity.CRITICAL)
        )

    @property
    def warning_count(self) -> int:
        """Count of warnings."""
        return len(self.warnings) + sum(
            1 for issue in self.issues if issue.severity == Severity.WARNING
        )

    def complete(self) -> None:
        """Mark verification as complete."""
        self.completed_at = datetime.utcnow()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def add_issue(
        self,
        issue_type: str,
        message: str,
        severity: Severity = Severity.ERROR,
        **kwargs: Any,
    ) -> None:
        """Add a safety issue to the result."""
        issue = SafetyIssue(
            issue_type=issue_type,
            message=message,
            severity=severity,
            **kwargs,
        )
        self.issues.append(issue)
        if severity in (Severity.ERROR, Severity.CRITICAL):
            self.passed = False

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"{self.verification_type.value.upper()}: {status}",
            self.message,
        ]

        if self.error_count > 0:
            lines.append(f"Errors: {self.error_count}")
        if self.warning_count > 0:
            lines.append(f"Warnings: {self.warning_count}")

        if self.duration_ms is not None:
            lines.append(f"Duration: {self.duration_ms}ms")

        for issue in self.issues:
            lines.append(f"  {issue.to_string()}")

        return "\n".join(lines)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "verification_type": "safety",
                    "passed": False,
                    "message": "Safety verification failed (1 issue)",
                    "critical": True,
                    "issues": [
                        {
                            "issue_type": "emergency_stop_modified",
                            "severity": "critical",
                            "message": "Emergency stop logic was modified",
                            "file_path": "src/safety.st",
                            "line_number": 42,
                        }
                    ],
                }
            ]
        }
    }
