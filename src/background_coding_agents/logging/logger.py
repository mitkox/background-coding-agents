"""
Structured logging implementation for industrial manufacturing.

Provides comprehensive logging with audit trail for regulatory compliance.
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

# Context variables for request/task tracking
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
site_name_var: ContextVar[str] = ContextVar("site_name", default="")
task_id_var: ContextVar[str] = ContextVar("task_id", default="")
user_var: ContextVar[str] = ContextVar("user", default="system")


class LogContext:
    """
    Context manager for adding context to logs.

    Usage:
        with LogContext(correlation_id="abc123", site_name="Plant-01"):
            logger.info("Processing site")
    """

    def __init__(
        self,
        correlation_id: str | None = None,
        site_name: str | None = None,
        task_id: str | None = None,
        user: str | None = None,
    ):
        self._tokens: list[Any] = []
        self._correlation_id = correlation_id or str(uuid.uuid4())[:8]
        self._site_name = site_name
        self._task_id = task_id
        self._user = user

    def __enter__(self) -> "LogContext":
        self._tokens.append(correlation_id_var.set(self._correlation_id))
        if self._site_name:
            self._tokens.append(site_name_var.set(self._site_name))
        if self._task_id:
            self._tokens.append(task_id_var.set(self._task_id))
        if self._user:
            self._tokens.append(user_var.set(self._user))
        return self

    def __exit__(self, *args: Any) -> None:
        for token in self._tokens:
            try:
                token.var.reset(token)
            except ValueError:
                pass

    @property
    def correlation_id(self) -> str:
        return self._correlation_id


def add_context_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add context variables to log events."""
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id

    site_name = site_name_var.get()
    if site_name:
        event_dict["site_name"] = site_name

    task_id = task_id_var.get()
    if task_id:
        event_dict["task_id"] = task_id

    user = user_var.get()
    if user:
        event_dict["user"] = user

    return event_dict


def add_timestamp_processor(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO timestamp to log events."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_service_info(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service information to log events."""
    event_dict["service"] = "background-coding-agents"
    event_dict["version"] = "0.1.0"
    return event_dict


def setup_logging(
    level: str = "INFO",
    format: str = "json",
    log_file: str | None = None,
    include_caller: bool = False,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format ('json' or 'text')
        log_file: Optional file path for log output
        include_caller: Include caller file/line info
    """
    # Shared processors for both stdlib and structlog
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        add_timestamp_processor,
        add_context_processor,
        add_service_info,
    ]

    if include_caller:
        shared_processors.append(structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ))

    # Configure structlog
    if format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (uses caller's module name if not specified)

    Returns:
        Configured structured logger
    """
    return structlog.get_logger(name)


class AuditLogger:
    """
    Specialized logger for audit trail events.

    Provides structured logging for regulatory compliance:
    - Change Authorization Requests (CARs)
    - Safety verification results
    - Human approvals
    - Deployments and rollbacks
    """

    def __init__(self, audit_file: str | Path | None = None):
        self.logger = get_logger("audit")
        self.audit_file = Path(audit_file) if audit_file else None

        if self.audit_file:
            self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def _write_audit_entry(self, entry: dict[str, Any]) -> None:
        """Write entry to audit file."""
        if self.audit_file:
            with open(self.audit_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")

    def log_migration_started(
        self,
        migration_name: str,
        target_sites: list[str],
        requested_by: str = "system",
        dry_run: bool = True,
    ) -> str:
        """Log migration start event."""
        event_id = str(uuid.uuid4())
        entry = {
            "event_type": "migration_started",
            "event_id": event_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "migration_name": migration_name,
            "target_sites": target_sites,
            "site_count": len(target_sites),
            "requested_by": requested_by,
            "dry_run": dry_run,
        }
        self.logger.info("Migration started", **entry)
        self._write_audit_entry(entry)
        return event_id

    def log_migration_completed(
        self,
        event_id: str,
        migration_name: str,
        success_count: int,
        failure_count: int,
        duration_seconds: float,
    ) -> None:
        """Log migration completion event."""
        entry = {
            "event_type": "migration_completed",
            "event_id": event_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "migration_name": migration_name,
            "success_count": success_count,
            "failure_count": failure_count,
            "duration_seconds": duration_seconds,
        }
        self.logger.info("Migration completed", **entry)
        self._write_audit_entry(entry)

    def log_change_request_created(
        self,
        car_id: str,
        site_name: str,
        migration_name: str,
        files_affected: list[str],
        changes_count: int,
    ) -> None:
        """Log CAR creation event."""
        entry = {
            "event_type": "car_created",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "car_id": car_id,
            "site_name": site_name,
            "migration_name": migration_name,
            "files_affected": files_affected,
            "changes_count": changes_count,
        }
        self.logger.info("Change request created", **entry)
        self._write_audit_entry(entry)

    def log_verification_result(
        self,
        car_id: str,
        verification_type: str,
        passed: bool,
        critical: bool = False,
        issues: list[dict[str, Any]] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Log verification result event."""
        entry = {
            "event_type": "verification_result",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "car_id": car_id,
            "verification_type": verification_type,
            "passed": passed,
            "critical": critical,
            "issues": issues or [],
            "duration_ms": duration_ms,
        }
        self.logger.info("Verification completed", **entry)
        self._write_audit_entry(entry)

    def log_safety_review(
        self,
        car_id: str,
        reviewer: str,
        approved: bool,
        notes: str = "",
    ) -> None:
        """Log safety review decision."""
        entry = {
            "event_type": "safety_review",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "car_id": car_id,
            "reviewer": reviewer,
            "approved": approved,
            "notes": notes,
        }
        self.logger.info("Safety review completed", **entry)
        self._write_audit_entry(entry)

    def log_human_approval(
        self,
        car_id: str,
        approver: str,
        approved: bool,
        notes: str = "",
    ) -> None:
        """Log human approval decision."""
        entry = {
            "event_type": "human_approval",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "car_id": car_id,
            "approver": approver,
            "approved": approved,
            "notes": notes,
        }
        self.logger.info("Human approval recorded", **entry)
        self._write_audit_entry(entry)

    def log_deployment(
        self,
        car_id: str,
        site_name: str,
        deployed_by: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Log deployment event."""
        entry = {
            "event_type": "deployment",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "car_id": car_id,
            "site_name": site_name,
            "deployed_by": deployed_by,
            "success": success,
            "error": error,
        }
        self.logger.info("Deployment executed", **entry)
        self._write_audit_entry(entry)

    def log_rollback(
        self,
        car_id: str,
        site_name: str,
        initiated_by: str,
        reason: str,
        success: bool,
    ) -> None:
        """Log rollback event."""
        entry = {
            "event_type": "rollback",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "car_id": car_id,
            "site_name": site_name,
            "initiated_by": initiated_by,
            "reason": reason,
            "success": success,
        }
        self.logger.warning("Rollback executed", **entry)
        self._write_audit_entry(entry)

    def log_llm_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        purpose: str,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Log LLM API call for tracing."""
        entry = {
            "event_type": "llm_call",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "latency_ms": latency_ms,
            "purpose": purpose,
            "success": success,
            "error": error,
        }
        log_func = self.logger.info if success else self.logger.error
        log_func("LLM call completed", **entry)
        self._write_audit_entry(entry)

    def log_safety_violation(
        self,
        site_name: str,
        violation_type: str,
        file_path: str,
        details: str,
        severity: str = "critical",
    ) -> None:
        """Log safety violation (always logged, never suppressed)."""
        entry = {
            "event_type": "safety_violation",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "site_name": site_name,
            "violation_type": violation_type,
            "file_path": file_path,
            "details": details,
            "severity": severity,
        }
        self.logger.critical("SAFETY VIOLATION DETECTED", **entry)
        self._write_audit_entry(entry)
