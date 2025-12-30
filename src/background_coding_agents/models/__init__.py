"""
Pydantic data models for type-safe, validated data structures.

Provides comprehensive models for:
- Site configuration
- Migration definitions
- Verification results
- Agent configuration
- LLM provider settings
- Audit logging
"""

from background_coding_agents.models.agent import (
    AgentConfig,
    AgentResult,
    AgentStatus,
    ExecutionPlan,
    PlanStep,
)
from background_coding_agents.models.changes import (
    ChangeRequest,
    ChangeStatus,
    PLCChange,
)
from background_coding_agents.models.llm import (
    LLMProviderConfig,
    LLMUsageStats,
)
from background_coding_agents.models.migration import (
    MigrationConfig,
    MigrationResult,
    MigrationStatus,
    SiteMigrationResult,
    TargetFilter,
)
from background_coding_agents.models.site import (
    PLCType,
    SafetyRating,
    SiteConfig,
)
from background_coding_agents.models.verification import (
    SafetyIssue,
    Severity,
    VerificationResult,
    VerificationType,
)

__all__ = [
    # Site models
    "SiteConfig",
    "PLCType",
    "SafetyRating",
    # Migration models
    "MigrationConfig",
    "MigrationResult",
    "MigrationStatus",
    "SiteMigrationResult",
    "TargetFilter",
    # Change models
    "PLCChange",
    "ChangeRequest",
    "ChangeStatus",
    # Verification models
    "VerificationResult",
    "VerificationType",
    "SafetyIssue",
    "Severity",
    # Agent models
    "AgentConfig",
    "AgentResult",
    "AgentStatus",
    "ExecutionPlan",
    "PlanStep",
    # LLM models
    "LLMProviderConfig",
    "LLMUsageStats",
]
