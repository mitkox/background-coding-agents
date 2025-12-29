"""
Abstract base class for LLM providers.

Supports both cloud APIs (Anthropic, OpenAI) and local LLMs
(llama.cpp, vLLM, OpenAI-compatible endpoints) for air-gapped environments.

Recommended local models:
- GLM-4.7: Excellent code generation and reasoning
- MiniMax-M2.1: Strong multilingual and code capabilities
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    # Cloud providers
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

    # Local providers (for air-gapped industrial environments)
    LLAMA_CPP = "llama_cpp"
    VLLM = "vllm"
    OPENAI_COMPATIBLE = "openai_compatible"


class MessageRole(str, Enum):
    """Standard message roles across providers."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A chat message for LLM conversation."""

    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {"role": self.role.value, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result


@dataclass
class ToolDefinition:
    """Definition of a tool/function the LLM can call."""

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str] = field(default_factory=list)

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required,
            },
        }


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    role: MessageRole = MessageRole.ASSISTANT
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    usage: dict[str, int] | None = None
    model: str | None = None
    provider: str | None = None
    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.tool_calls)

    @property
    def input_tokens(self) -> int:
        """Get input token count."""
        return self.usage.get("input_tokens", 0) if self.usage else 0

    @property
    def output_tokens(self) -> int:
        """Get output token count."""
        return self.usage.get("output_tokens", 0) if self.usage else 0


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""

    provider: ProviderType
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0

    # Local LLM specific
    n_ctx: int = 4096  # Context window for llama.cpp
    n_gpu_layers: int = -1  # GPU layers for llama.cpp (-1 = all)
    rope_scaling: str | None = None  # For extended context

    # Rate limiting
    requests_per_minute: int = 60

    # Additional provider-specific options
    extra_options: dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Supports:
    - Cloud APIs: Anthropic Claude, OpenAI GPT
    - Local LLMs: llama.cpp, vLLM (GLM-4.7, MiniMax-M2.1)
    - OpenAI-compatible APIs: Custom inference servers
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Any = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        ...

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """Return True if this is a local LLM provider."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider (connect, load model, etc.)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup resources."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: Conversation history
            tools: Available tools for function calling
            system_prompt: System instructions
            **kwargs: Additional provider-specific options

        Returns:
            Standardized LLM response
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a response from the LLM.

        Yields:
            Text chunks as they're generated
        """
        ...

    async def health_check(self) -> dict[str, Any]:
        """
        Check if the provider is healthy and available.

        Returns:
            Health status with provider info
        """
        try:
            # Simple test: send a minimal prompt
            response = await self.generate(
                messages=[Message(role=MessageRole.USER, content="Hi")],
                max_tokens=10,
            )
            return {
                "healthy": True,
                "provider": self.provider_name,
                "model": self.config.model,
                "is_local": self.is_local,
                "latency_ms": None,  # Could add timing
            }
        except Exception as e:
            return {
                "healthy": False,
                "provider": self.provider_name,
                "error": str(e),
            }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model})"
