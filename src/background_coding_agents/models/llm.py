"""
LLM provider configuration models.
"""

from typing import Any

from pydantic import BaseModel, Field

from background_coding_agents.llm.base import ProviderType


class LLMProviderConfig(BaseModel):
    """
    Configuration for an LLM provider.

    Supports both cloud and local providers for industrial environments.
    """

    # Provider selection
    provider: ProviderType = Field(
        default=ProviderType.ANTHROPIC, description="LLM provider type"
    )
    model: str = Field(..., description="Model name or path")

    # Authentication (cloud providers)
    api_key: str | None = Field(
        default=None, description="API key (reads from env if not specified)"
    )

    # Connection settings
    base_url: str | None = Field(
        default=None, description="Base URL for API (required for local providers)"
    )
    timeout: int = Field(default=120, description="Request timeout in seconds", ge=1)
    max_retries: int = Field(default=3, description="Maximum retry attempts", ge=0)
    retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )

    # Generation parameters
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)

    # Local model settings (llama.cpp)
    n_ctx: int = Field(
        default=4096, description="Context window size for local models", ge=512
    )
    n_gpu_layers: int = Field(
        default=-1, description="GPU layers for local models (-1 = all)"
    )
    rope_scaling: str | None = Field(
        default=None, description="RoPE scaling type for extended context"
    )

    # Rate limiting
    requests_per_minute: int = Field(
        default=60, description="Rate limit (requests per minute)", ge=1
    )

    # Extra options
    extra_options: dict[str, Any] = Field(
        default_factory=dict, description="Additional provider-specific options"
    )

    @property
    def is_local(self) -> bool:
        """Check if this is a local provider."""
        return self.provider in (
            ProviderType.LLAMA_CPP,
            ProviderType.VLLM,
        )

    @property
    def requires_api_key(self) -> bool:
        """Check if this provider requires an API key."""
        return self.provider in (ProviderType.ANTHROPIC, ProviderType.OPENAI)

    def get_env_api_key_name(self) -> str | None:
        """Get environment variable name for API key."""
        mapping = {
            ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
            ProviderType.OPENAI: "OPENAI_API_KEY",
        }
        return mapping.get(self.provider)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "provider": "vllm",
                    "model": "THUDM/glm-4.7",
                    "base_url": "http://localhost:8000",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
                {
                    "provider": "llama_cpp",
                    "model": "/models/MiniMax-M2.1.Q4_K_M.gguf",
                    "n_gpu_layers": -1,
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
                {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            ]
        }
    }


class LLMUsageStats(BaseModel):
    """
    Statistics for LLM usage tracking.

    Useful for cost monitoring and optimization.
    """

    provider: str
    model: str

    # Token counts
    total_input_tokens: int = Field(default=0, ge=0)
    total_output_tokens: int = Field(default=0, ge=0)

    # Request counts
    total_requests: int = Field(default=0, ge=0)
    successful_requests: int = Field(default=0, ge=0)
    failed_requests: int = Field(default=0, ge=0)
    retried_requests: int = Field(default=0, ge=0)

    # Timing
    total_latency_ms: int = Field(default=0, ge=0)

    # Cost tracking (for cloud providers)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def success_rate(self) -> float:
        """Request success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_latency_ms(self) -> float:
        """Average latency per request."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def add_request(
        self,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        success: bool = True,
        retried: bool = False,
    ) -> None:
        """Record a completed request."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_latency_ms += latency_ms
        else:
            self.failed_requests += 1
        if retried:
            self.retried_requests += 1

    def to_summary(self) -> str:
        """Generate usage summary."""
        lines = [
            f"Provider: {self.provider}",
            f"Model: {self.model}",
            f"Total requests: {self.total_requests}",
            f"Success rate: {self.success_rate:.1f}%",
            f"Total tokens: {self.total_tokens:,}",
            f"  Input: {self.total_input_tokens:,}",
            f"  Output: {self.total_output_tokens:,}",
            f"Avg latency: {self.average_latency_ms:.0f}ms",
        ]
        if self.estimated_cost_usd > 0:
            lines.append(f"Est. cost: ${self.estimated_cost_usd:.4f}")
        return "\n".join(lines)
