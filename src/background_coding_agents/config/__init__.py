"""
Configuration management with validation.

Provides environment-aware, validated configuration using Pydantic Settings.
Supports multiple configuration sources: environment variables, YAML files, and programmatic overrides.
"""

from background_coding_agents.config.settings import (
    AgentSettings,
    AppSettings,
    LLMSettings,
    LoggingSettings,
    SafetySettings,
    TelemetrySettings,
    VerificationSettings,
    get_settings,
    reload_settings,
)

__all__ = [
    "AppSettings",
    "LLMSettings",
    "AgentSettings",
    "VerificationSettings",
    "SafetySettings",
    "LoggingSettings",
    "TelemetrySettings",
    "get_settings",
    "reload_settings",
]
