"""
Application settings using Pydantic Settings.

Configuration hierarchy (highest priority first):
1. Environment variables
2. .env file
3. Configuration YAML file
4. Default values
"""

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from background_coding_agents.llm.base import ProviderType


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Log level options."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LLMSettings(BaseSettings):
    """
    LLM provider settings.

    Supports cloud and local providers for industrial environments.
    """

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider selection
    provider: ProviderType = Field(
        default=ProviderType.ANTHROPIC,
        description="LLM provider (anthropic, openai, llama_cpp, vllm, openai_compatible)",
    )
    model: str | None = Field(
        default=None,
        description="Model name (uses provider default if not specified)",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for API (required for local providers)",
    )

    # Generation parameters
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)

    # Connection settings
    timeout: int = Field(default=120, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, ge=0.0)

    # Rate limiting
    requests_per_minute: int = Field(default=60, ge=1)

    # Local model settings
    n_ctx: int = Field(default=4096, ge=512, description="Context window for local models")
    n_gpu_layers: int = Field(default=-1, description="GPU layers (-1 = all)")


class AgentSettings(BaseSettings):
    """Agent execution settings."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_turns: int = Field(default=10, ge=1, le=100)
    max_retries: int = Field(default=3, ge=0)
    timeout: int = Field(default=300, ge=30, description="Total execution timeout in seconds")

    # Tools available to agents
    tools: list[str] = Field(
        default=["verify", "git_diff", "ripgrep"],
    )

    # Concurrent execution
    max_concurrent_sites: int = Field(default=5, ge=1)
    max_concurrent_verifiers: int = Field(default=3, ge=1)

    @field_validator("tools", mode="before")
    @classmethod
    def parse_tools(cls, v: Any) -> list[str]:
        """Parse tools from comma-separated string."""
        if isinstance(v, str):
            return [t.strip() for t in v.split(",")]
        return v


class VerificationSettings(BaseSettings):
    """Verification system settings."""

    model_config = SettingsConfigDict(
        env_prefix="VERIFICATION_",
        extra="ignore",
    )

    # Compiler settings
    compiler_timeout: int = Field(default=300, ge=30)
    siemens_tia_path: str | None = Field(default=None)
    rockwell_studio5000_path: str | None = Field(default=None)
    codesys_path: str | None = Field(default=None)

    # Safety verification
    safety_timeout: int = Field(default=600, ge=60)
    enable_safety_verifier: bool = Field(default=True)

    # Simulation
    simulation_timeout: int = Field(default=900, ge=60)
    enable_simulation: bool = Field(default=False)
    plcsim_path: str | None = Field(default=None)

    # LLM Judge
    enable_llm_judge: bool = Field(default=True)
    judge_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    judge_model: str | None = Field(default=None, description="Model for LLM judge")


class SafetySettings(BaseSettings):
    """Safety-specific settings for manufacturing environments."""

    model_config = SettingsConfigDict(
        env_prefix="SAFETY_",
        extra="ignore",
    )

    # Safety review requirements
    require_safety_review: bool = Field(default=True)
    require_human_approval: bool = Field(default=True)

    # Forbidden patterns (regex)
    forbidden_patterns: list[str] = Field(
        default=[
            "E_STOP",
            "EMERGENCY_STOP",
            "SAFETY_STOP",
            "FORCE",
            r"DISABLE.*SAFETY",
            r"BYPASS.*GUARD",
        ],
    )

    # Protected files
    protected_files: list[str] = Field(
        default=[
            "certified_safety_logic.st",
            "sil3_rated_module.st",
        ],
    )

    # Minimum SIL rating for enhanced review
    enhanced_review_sil: str = Field(default="SIL-2")

    @field_validator("forbidden_patterns", "protected_files", mode="before")
    @classmethod
    def parse_list(cls, v: Any) -> list[str]:
        """Parse list from comma-separated string."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v


class LoggingSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
    )

    level: LogLevel = Field(default=LogLevel.INFO)
    format: str = Field(default="json", description="Log format: json or text")

    # File logging
    file: str | None = Field(default=None, description="Log file path")
    rotation: str = Field(default="10MB")
    retention: int = Field(default=30, description="Log retention in days")

    # Structured logging options
    include_timestamp: bool = Field(default=True)
    include_correlation_id: bool = Field(default=True)
    include_caller: bool = Field(default=False)


class TelemetrySettings(BaseSettings):
    """Telemetry and observability settings."""

    model_config = SettingsConfigDict(
        env_prefix="TELEMETRY_",
        extra="ignore",
    )

    enabled: bool = Field(default=True)

    # MLflow
    mlflow_enabled: bool = Field(default=True)
    mlflow_tracking_uri: str = Field(default="http://localhost:5000")
    mlflow_experiment_name: str = Field(default="background-coding-agents")

    # Tracing
    trace_llm_calls: bool = Field(default=True)
    trace_verifications: bool = Field(default=True)


class AppSettings(BaseSettings):
    """
    Main application settings.

    Aggregates all setting categories and provides unified access.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)

    # Application paths
    config_path: Path = Field(
        default=Path("fleet-manager/config.yaml"),
        description="Path to fleet manager configuration",
    )
    migrations_path: Path = Field(
        default=Path("fleet-manager/migrations"),
        description="Path to migration definitions",
    )

    # API Keys (from environment)
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # Nested settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    verification: VerificationSettings = Field(default_factory=VerificationSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)

    # Mock mode for testing
    use_mock_llm: bool = Field(default=False)
    use_mock_compiler: bool = Field(default=False)

    @field_validator("config_path", "migrations_path", mode="before")
    @classmethod
    def parse_path(cls, v: Any) -> Path:
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v

    def get_llm_api_key(self, provider: ProviderType | None = None) -> str | None:
        """Get API key for the specified or configured provider."""
        provider = provider or self.llm.provider

        if provider == ProviderType.ANTHROPIC:
            return self.anthropic_api_key
        elif provider == ProviderType.OPENAI:
            return self.openai_api_key

        return None

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        # Ensure API key is available for cloud providers
        if self.llm.provider in (ProviderType.ANTHROPIC, ProviderType.OPENAI):
            api_key = self.get_llm_api_key()
            if not api_key and not self.use_mock_llm:
                import warnings

                warnings.warn(
                    f"No API key found for {self.llm.provider.value}. "
                    f"Set {self.llm.provider.value.upper()}_API_KEY environment variable.",
                    UserWarning,
                    stacklevel=2,
                )


# Singleton settings instance
_settings: AppSettings | None = None


@lru_cache
def get_settings() -> AppSettings:
    """
    Get application settings (singleton).

    Returns cached settings instance, creating it if necessary.
    """
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    """
    Reload settings (useful for testing).

    Clears cache and creates new settings instance.
    """
    global _settings
    get_settings.cache_clear()
    _settings = AppSettings()
    return _settings


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Used for loading fleet manager and migration configurations.
    """
    import yaml

    with open(config_path) as f:
        return yaml.safe_load(f) or {}
