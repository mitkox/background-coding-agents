"""
Structured logging with context and audit trail.

Provides production-quality logging with:
- Structured JSON output for log aggregation
- Context tracking with correlation IDs
- Audit logging for regulatory compliance
- Integration with observability platforms
"""

from background_coding_agents.logging.logger import (
    AuditLogger,
    LogContext,
    get_logger,
    setup_logging,
)

__all__ = [
    "get_logger",
    "setup_logging",
    "LogContext",
    "AuditLogger",
]
