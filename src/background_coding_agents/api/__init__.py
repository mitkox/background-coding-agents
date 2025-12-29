"""
REST API for Industrial Manufacturing Integration.

Provides endpoints for:
- SCADA/MES system integration
- Migration management
- Site configuration
- Health monitoring
- Webhook notifications
"""

from background_coding_agents.api.app import create_app
from background_coding_agents.api.routes import router

__all__ = ["create_app", "router"]
