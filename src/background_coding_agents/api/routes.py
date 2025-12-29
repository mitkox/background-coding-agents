"""
API routes for fleet manager operations.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from background_coding_agents.config import get_settings
from background_coding_agents.fleet_manager.cli import FleetManager
from background_coding_agents.llm import LLMProviderFactory, ProviderType
from background_coding_agents.logging import get_logger
from background_coding_agents.models import (
    MigrationConfig,
    MigrationResult,
    MigrationStatus,
    SiteConfig,
)

logger = get_logger(__name__)

router = APIRouter()


# ============ Request/Response Models ============


class MigrationRequest(BaseModel):
    """Request to start a migration."""

    migration_name: str = Field(..., description="Name of migration to execute")
    dry_run: bool = Field(default=True, description="Run without making changes")
    target_sites: list[str] | None = Field(
        default=None, description="Specific sites to target"
    )
    provider: str | None = Field(
        default=None, description="LLM provider to use (overrides config)"
    )
    model: str | None = Field(default=None, description="Model name (overrides config)")


class MigrationResponse(BaseModel):
    """Response for migration operations."""

    job_id: str
    migration_name: str
    status: str
    message: str
    started_at: datetime


class MigrationStatusResponse(BaseModel):
    """Response for migration status query."""

    job_id: str
    migration_name: str
    status: str
    total_sites: int
    successful_sites: int
    failed_sites: int
    started_at: datetime
    completed_at: datetime | None
    results: list[dict[str, Any]] | None = None


class SiteResponse(BaseModel):
    """Response for site information."""

    name: str
    location: str
    plc_type: str
    firmware_version: str
    safety_rating: str
    line_type: str


class HealthResponse(BaseModel):
    """Detailed health check response."""

    status: str
    version: str
    environment: str
    llm_provider: str
    llm_model: str | None
    llm_healthy: bool
    sites_configured: int


class ProviderInfo(BaseModel):
    """LLM provider information."""

    provider: str
    model: str
    is_local: bool
    healthy: bool


# ============ In-Memory Job Storage ============
# In production, use Redis or database

_jobs: dict[str, dict[str, Any]] = {}
_job_counter = 0


def _create_job_id() -> str:
    """Create unique job ID."""
    global _job_counter
    _job_counter += 1
    return f"job-{_job_counter:06d}"


# ============ Routes ============


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def detailed_health() -> HealthResponse:
    """
    Detailed health check with LLM provider status.

    Returns system health including LLM provider availability.
    """
    settings = get_settings()

    # Check LLM provider health
    llm_healthy = False
    try:
        provider = LLMProviderFactory.create_from_env()
        await provider.initialize()
        health = await provider.health_check()
        llm_healthy = health.get("healthy", False)
        await provider.close()
    except Exception as e:
        logger.warning("LLM health check failed", error=str(e))

    # Count configured sites
    sites_count = 0
    try:
        config_path = settings.config_path
        if config_path.exists():
            import yaml

            with open(config_path) as f:
                config = yaml.safe_load(f)
            sites_count = len(config.get("sites", []))
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.environment.value,
        llm_provider=settings.llm.provider.value,
        llm_model=settings.llm.model,
        llm_healthy=llm_healthy,
        sites_configured=sites_count,
    )


@router.get("/providers", response_model=list[ProviderInfo], tags=["LLM Providers"])
async def list_providers() -> list[ProviderInfo]:
    """
    List available LLM providers and their status.

    Returns information about all supported providers including
    whether they are currently available.
    """
    providers = []

    for provider_type in ProviderType:
        is_local = provider_type in (
            ProviderType.LLAMA_CPP,
            ProviderType.VLLM,
        )

        healthy = False
        model = None

        try:
            if provider_type == ProviderType.VLLM:
                import socket

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                healthy = sock.connect_ex(("localhost", 8000)) == 0
                sock.close()
                model = "THUDM/glm-4.7"  # Recommended local model
            elif provider_type == ProviderType.LLAMA_CPP:
                # llama.cpp is a library, assume available if configured
                model = "glm-4.7.Q4_K_M.gguf"  # Recommended local model
            elif provider_type == ProviderType.ANTHROPIC:
                import os

                healthy = bool(os.getenv("ANTHROPIC_API_KEY"))
                model = "claude-sonnet-4-20250514"
            elif provider_type == ProviderType.OPENAI:
                import os

                healthy = bool(os.getenv("OPENAI_API_KEY"))
                model = "gpt-4o"
        except Exception:
            pass

        providers.append(
            ProviderInfo(
                provider=provider_type.value,
                model=model or "default",
                is_local=is_local,
                healthy=healthy,
            )
        )

    return providers


@router.get("/sites", response_model=list[SiteResponse], tags=["Sites"])
async def list_sites() -> list[SiteResponse]:
    """
    List all configured manufacturing sites.

    Returns the list of sites available for migrations.
    """
    settings = get_settings()

    try:
        import yaml

        with open(settings.config_path) as f:
            config = yaml.safe_load(f)

        sites = []
        for site_data in config.get("sites", []):
            sites.append(
                SiteResponse(
                    name=site_data["name"],
                    location=site_data["location"],
                    plc_type=site_data["plc_type"],
                    firmware_version=site_data["firmware_version"],
                    safety_rating=site_data.get("safety_rating", "None"),
                    line_type=site_data.get("line_type", "General"),
                )
            )
        return sites

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Configuration file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sites/{site_name}", response_model=SiteResponse, tags=["Sites"])
async def get_site(site_name: str) -> SiteResponse:
    """
    Get details for a specific site.

    Args:
        site_name: Name of the site to retrieve
    """
    sites = await list_sites()
    for site in sites:
        if site.name == site_name:
            return site
    raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")


@router.get("/migrations", tags=["Migrations"])
async def list_migrations() -> list[dict[str, str]]:
    """
    List available migration definitions.

    Returns all migration YAML files available for execution.
    """
    settings = get_settings()
    migrations_path = settings.migrations_path

    if not migrations_path.exists():
        return []

    migrations = []
    for path in migrations_path.glob("*.yaml"):
        migrations.append({"name": path.stem, "path": str(path)})
    for path in migrations_path.glob("*.yml"):
        migrations.append({"name": path.stem, "path": str(path)})

    return migrations


@router.post("/migrations/run", response_model=MigrationResponse, tags=["Migrations"])
async def run_migration(
    request: MigrationRequest, background_tasks: BackgroundTasks
) -> MigrationResponse:
    """
    Start a migration execution.

    Starts the migration in the background and returns a job ID
    that can be used to track progress.
    """
    job_id = _create_job_id()
    started_at = datetime.utcnow()

    # Store job info
    _jobs[job_id] = {
        "job_id": job_id,
        "migration_name": request.migration_name,
        "status": "pending",
        "started_at": started_at,
        "completed_at": None,
        "result": None,
        "request": request.model_dump(),
    }

    # Start migration in background
    background_tasks.add_task(_run_migration_task, job_id, request)

    logger.info(
        "Migration job started",
        job_id=job_id,
        migration=request.migration_name,
        dry_run=request.dry_run,
    )

    return MigrationResponse(
        job_id=job_id,
        migration_name=request.migration_name,
        status="pending",
        message="Migration started in background",
        started_at=started_at,
    )


async def _run_migration_task(job_id: str, request: MigrationRequest) -> None:
    """Background task to run migration."""
    import os

    # Override environment if provider specified
    if request.provider:
        os.environ["LLM_PROVIDER"] = request.provider
    if request.model:
        os.environ["LLM_MODEL"] = request.model

    try:
        _jobs[job_id]["status"] = "running"

        settings = get_settings()
        manager = FleetManager(settings.config_path)

        result = await manager.run_migration(
            migration_name=request.migration_name,
            dry_run=request.dry_run,
            target_sites=request.target_sites,
        )

        _jobs[job_id]["status"] = "completed" if result.failed_sites == 0 else "partial"
        _jobs[job_id]["completed_at"] = datetime.utcnow()
        _jobs[job_id]["result"] = result.model_dump()

        logger.info(
            "Migration job completed",
            job_id=job_id,
            success_count=result.successful_sites,
            failed_count=result.failed_sites,
        )

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["completed_at"] = datetime.utcnow()
        _jobs[job_id]["error"] = str(e)

        logger.exception("Migration job failed", job_id=job_id, error=str(e))


@router.get(
    "/migrations/jobs/{job_id}",
    response_model=MigrationStatusResponse,
    tags=["Migrations"],
)
async def get_migration_status(job_id: str) -> MigrationStatusResponse:
    """
    Get status of a migration job.

    Args:
        job_id: Job ID returned from run_migration
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job = _jobs[job_id]
    result = job.get("result")

    return MigrationStatusResponse(
        job_id=job_id,
        migration_name=job["migration_name"],
        status=job["status"],
        total_sites=result.get("total_sites", 0) if result else 0,
        successful_sites=result.get("successful_sites", 0) if result else 0,
        failed_sites=result.get("failed_sites", 0) if result else 0,
        started_at=job["started_at"],
        completed_at=job.get("completed_at"),
        results=result.get("site_results") if result else None,
    )


@router.get("/migrations/jobs", tags=["Migrations"])
async def list_jobs(
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """
    List migration jobs.

    Args:
        status: Filter by job status (pending, running, completed, failed)
        limit: Maximum number of jobs to return
    """
    jobs = list(_jobs.values())

    if status:
        jobs = [j for j in jobs if j["status"] == status]

    # Sort by started_at descending
    jobs.sort(key=lambda j: j["started_at"], reverse=True)

    return jobs[:limit]


@router.delete("/migrations/jobs/{job_id}", tags=["Migrations"])
async def cancel_job(job_id: str) -> dict[str, str]:
    """
    Cancel a running migration job.

    Note: This only marks the job as cancelled. Running tasks
    will complete but no new sites will be processed.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job = _jobs[job_id]
    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400, detail=f"Job already {job['status']}, cannot cancel"
        )

    job["status"] = "cancelled"
    job["completed_at"] = datetime.utcnow()

    logger.info("Migration job cancelled", job_id=job_id)

    return {"message": f"Job {job_id} cancelled"}


@router.post("/verify", tags=["Verification"])
async def run_verification(
    site_name: str = Query(..., description="Site to verify"),
    verification_type: str = Query(
        default="all", description="Type: compile, safety, or all"
    ),
) -> dict[str, Any]:
    """
    Run verification checks on a site.

    Useful for pre-flight checks before running migrations.
    """
    from background_coding_agents.verifiers.plc_compiler_verifier import (
        PLCCompilerVerifier,
    )
    from background_coding_agents.verifiers.safety_verifier import SafetyVerifier

    # Get site config
    sites = await list_sites()
    site_data = None
    for site in sites:
        if site.name == site_name:
            site_data = site.model_dump()
            break

    if not site_data:
        raise HTTPException(status_code=404, detail=f"Site '{site_name}' not found")

    results = {}

    if verification_type in ("compile", "all"):
        try:
            compiler = PLCCompilerVerifier()
            results["compile"] = await compiler.verify({}, site_data)
        except Exception as e:
            results["compile"] = {"passed": False, "error": str(e)}

    if verification_type in ("safety", "all"):
        try:
            safety = SafetyVerifier()
            results["safety"] = await safety.verify({}, site_data)
        except Exception as e:
            results["safety"] = {"passed": False, "error": str(e)}

    return {"site": site_name, "verification_type": verification_type, "results": results}
