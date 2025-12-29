"""
FastAPI application for industrial manufacturing integration.

Provides REST API endpoints for SCADA/MES systems to interact with
the background coding agents fleet manager.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from background_coding_agents.config import get_settings
from background_coding_agents.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    setup_logging(
        level=settings.logging.level.value,
        format=settings.logging.format,
    )
    logger.info("API server starting", environment=settings.environment.value)
    yield
    # Shutdown
    logger.info("API server shutting down")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="Background Coding Agents API",
        description="""
REST API for Industrial Manufacturing Code Automation.

This API enables SCADA/MES system integration with the background coding agents
fleet manager for automated PLC code migrations across manufacturing sites.

## Features

- **Migrations**: Execute and monitor fleet-wide code migrations
- **Sites**: Manage manufacturing site configurations
- **Verifications**: Run safety and compliance checks
- **Health**: Monitor system and LLM provider health
- **Webhooks**: Receive notifications for migration events

## Authentication

API endpoints require authentication via API key in the `X-API-Key` header.
        """,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from background_coding_agents.api.routes import router

    app.include_router(router, prefix="/api/v1")

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.debug else "An error occurred",
            },
        )

    # Health check endpoint (no auth required)
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """Basic health check endpoint."""
        return {"status": "healthy", "version": "0.1.0"}

    return app


# Create app instance for uvicorn
app = create_app()
