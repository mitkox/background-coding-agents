"""
LLM Provider Factory.

Creates and manages LLM provider instances based on configuration.
Supports automatic provider selection and failover.

Local providers for air-gapped industrial environments:
- llama.cpp: GLM-4.7, MiniMax-M2.1 in GGUF format
- vLLM: GLM-4.7, MiniMax-M2.1 for high-throughput
"""

import logging
import os
from typing import Any

from background_coding_agents.llm.base import BaseLLMProvider, LLMConfig, ProviderType
from background_coding_agents.llm.providers.anthropic import AnthropicProvider
from background_coding_agents.llm.providers.llama_cpp import LlamaCppProvider
from background_coding_agents.llm.providers.openai import OpenAIProvider
from background_coding_agents.llm.providers.openai_compatible import OpenAICompatibleProvider
from background_coding_agents.llm.providers.vllm import VLLMProvider

logger = logging.getLogger(__name__)


# Provider class mapping
PROVIDER_CLASSES: dict[ProviderType, type[BaseLLMProvider]] = {
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.LLAMA_CPP: LlamaCppProvider,
    ProviderType.VLLM: VLLMProvider,
    ProviderType.OPENAI_COMPATIBLE: OpenAICompatibleProvider,
}

# Default models for each provider
DEFAULT_MODELS: dict[ProviderType, str] = {
    ProviderType.ANTHROPIC: "claude-sonnet-4-20250514",
    ProviderType.OPENAI: "gpt-4o",
    ProviderType.LLAMA_CPP: "models/glm-4.7.Q4_K_M.gguf",
    ProviderType.VLLM: "THUDM/glm-4.7",
    ProviderType.OPENAI_COMPATIBLE: "glm-4.7",
}

# Recommended industrial models by provider
# GLM-4.7 and MiniMax-M2.1 are optimized for code generation and industrial use
INDUSTRIAL_MODELS: dict[ProviderType, list[dict[str, str]]] = {
    ProviderType.ANTHROPIC: [
        {"model": "claude-opus-4-20250514", "use_case": "Complex reasoning, safety-critical"},
        {"model": "claude-sonnet-4-20250514", "use_case": "General code transformation"},
    ],
    ProviderType.OPENAI: [
        {"model": "gpt-4o", "use_case": "General purpose, LLM judge"},
        {"model": "gpt-4-turbo", "use_case": "Complex reasoning"},
    ],
    ProviderType.LLAMA_CPP: [
        {"model": "glm-4.7.Q4_K_M.gguf", "use_case": "Code generation, edge deployment"},
        {"model": "glm-4.7.Q5_K_M.gguf", "use_case": "Higher quality, more VRAM"},
        {"model": "MiniMax-M2.1.Q4_K_M.gguf", "use_case": "Multilingual, code generation"},
        {"model": "MiniMax-M2.1.Q5_K_M.gguf", "use_case": "Higher quality inference"},
    ],
    ProviderType.VLLM: [
        {"model": "THUDM/glm-4.7", "use_case": "High-throughput code generation"},
        {"model": "MiniMaxAI/MiniMax-M2.1", "use_case": "Multilingual industrial use"},
    ],
    ProviderType.OPENAI_COMPATIBLE: [
        {"model": "glm-4.7", "use_case": "Local inference server"},
        {"model": "minimax-m2.1", "use_case": "Local inference server"},
    ],
}


class LLMProviderFactory:
    """
    Factory for creating and managing LLM provider instances.

    Supports:
    - Creating providers from configuration
    - Environment-based configuration
    - Automatic provider selection
    - Provider caching and reuse
    - Health checking

    Local providers (llama.cpp, vLLM) recommended for:
    - Air-gapped industrial environments
    - Edge deployment on industrial PCs
    - Maximum control over inference
    """

    _instances: dict[str, BaseLLMProvider] = {}

    @classmethod
    def create(
        cls,
        provider: ProviderType | str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> BaseLLMProvider:
        """
        Create an LLM provider instance.

        Args:
            provider: Provider type (anthropic, openai, llama_cpp, vllm, openai_compatible)
            model: Model name/path (uses default if not specified)
            api_key: API key (reads from env if not specified)
            base_url: Base URL for API (provider-specific defaults)
            **kwargs: Additional provider-specific options

        Returns:
            Configured LLM provider instance
        """
        # Normalize provider type
        if isinstance(provider, str):
            provider = ProviderType(provider.lower())

        # Get provider class
        provider_class = PROVIDER_CLASSES.get(provider)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider}")

        # Build configuration
        config = cls._build_config(provider, model, api_key, base_url, **kwargs)

        # Create provider instance
        instance = provider_class(config)

        logger.info(f"Created {provider.value} provider with model {config.model}")

        return instance

    @classmethod
    def create_from_env(cls, provider: ProviderType | str | None = None) -> BaseLLMProvider:
        """
        Create a provider using environment variables.

        Environment variables:
        - LLM_PROVIDER: Provider type (default: auto-detect)
        - LLM_MODEL: Model name
        - LLM_BASE_URL: Base URL for API
        - ANTHROPIC_API_KEY: Anthropic API key
        - OPENAI_API_KEY: OpenAI API key
        - VLLM_BASE_URL: vLLM server URL
        - LLAMA_CPP_MODEL_PATH: Path to GGUF model
        """
        if provider is None:
            provider_str = os.getenv("LLM_PROVIDER")
            if provider_str:
                provider = ProviderType(provider_str.lower())
            else:
                provider = cls._auto_detect_provider()

        if isinstance(provider, str):
            provider = ProviderType(provider.lower())

        model = os.getenv("LLM_MODEL")
        base_url = os.getenv("LLM_BASE_URL")

        # Provider-specific environment variables
        api_key = None
        if provider == ProviderType.ANTHROPIC:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider == ProviderType.OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == ProviderType.VLLM:
            base_url = base_url or os.getenv("VLLM_BASE_URL", "http://localhost:8000")
        elif provider == ProviderType.LLAMA_CPP:
            model = model or os.getenv("LLAMA_CPP_MODEL_PATH")
        elif provider == ProviderType.OPENAI_COMPATIBLE:
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL")

        return cls.create(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    @classmethod
    def get_or_create(
        cls,
        instance_id: str,
        provider: ProviderType | str,
        **kwargs: Any,
    ) -> BaseLLMProvider:
        """
        Get an existing provider instance or create a new one.

        Useful for reusing providers across multiple agents.
        """
        if instance_id in cls._instances:
            return cls._instances[instance_id]

        instance = cls.create(provider, **kwargs)
        cls._instances[instance_id] = instance
        return instance

    @classmethod
    async def close_all(cls) -> None:
        """Close all cached provider instances."""
        for instance_id, instance in cls._instances.items():
            try:
                await instance.close()
                logger.info(f"Closed provider instance: {instance_id}")
            except Exception as e:
                logger.warning(f"Error closing provider {instance_id}: {e}")
        cls._instances.clear()

    @classmethod
    def _build_config(
        cls,
        provider: ProviderType,
        model: str | None,
        api_key: str | None,
        base_url: str | None,
        **kwargs: Any,
    ) -> LLMConfig:
        """Build LLMConfig from parameters."""
        # Use default model if not specified
        if not model:
            model = DEFAULT_MODELS.get(provider, "default")

        return LLMConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 4096),
            timeout=kwargs.get("timeout", 120),
            max_retries=kwargs.get("max_retries", 3),
            retry_delay=kwargs.get("retry_delay", 1.0),
            n_ctx=kwargs.get("n_ctx", 4096),
            n_gpu_layers=kwargs.get("n_gpu_layers", -1),
            requests_per_minute=kwargs.get("requests_per_minute", 60),
            extra_options=kwargs.get("extra_options", {}),
        )

    @classmethod
    def _auto_detect_provider(cls) -> ProviderType:
        """
        Auto-detect the best available provider.

        Priority:
        1. Local providers (vLLM, llama.cpp) for air-gapped environments
        2. Cloud providers (Anthropic, OpenAI) if API keys available
        """
        # Check for local providers first (industrial preference)
        if cls._check_vllm_available():
            logger.info("Auto-detected vLLM (local)")
            return ProviderType.VLLM

        # Check for cloud providers
        if os.getenv("ANTHROPIC_API_KEY"):
            logger.info("Auto-detected Anthropic (cloud)")
            return ProviderType.ANTHROPIC

        if os.getenv("OPENAI_API_KEY"):
            logger.info("Auto-detected OpenAI (cloud)")
            return ProviderType.OPENAI

        # Default to vLLM (user should start it with GLM-4.7 or MiniMax-M2.1)
        logger.warning(
            "No LLM provider configured. Defaulting to vLLM. "
            "Start vLLM with GLM-4.7 or MiniMax-M2.1, or set ANTHROPIC_API_KEY/OPENAI_API_KEY."
        )
        return ProviderType.VLLM

    @classmethod
    def _check_vllm_available(cls) -> bool:
        """Check if vLLM server is available."""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 8000))
            sock.close()
            return result == 0
        except Exception:
            return False

    @classmethod
    def list_recommended_models(
        cls, provider: ProviderType | str | None = None
    ) -> dict[str, list[dict[str, str]]]:
        """List recommended models for industrial use cases."""
        if provider:
            if isinstance(provider, str):
                provider = ProviderType(provider.lower())
            return {provider.value: INDUSTRIAL_MODELS.get(provider, [])}

        return {p.value: models for p, models in INDUSTRIAL_MODELS.items()}


def create_provider(
    provider: str = "auto",
    model: str | None = None,
    **kwargs: Any,
) -> BaseLLMProvider:
    """
    Convenience function to create an LLM provider.

    Args:
        provider: Provider name or "auto" for auto-detection
        model: Model name/path
        **kwargs: Additional options

    Returns:
        Configured LLM provider

    Examples:
        # Auto-detect best available provider
        provider = create_provider("auto")

        # Use vLLM with GLM-4.7
        provider = create_provider("vllm", model="THUDM/glm-4.7")

        # Use llama.cpp with MiniMax-M2.1
        provider = create_provider("llama_cpp", model="models/MiniMax-M2.1.Q4_K_M.gguf")
    """
    if provider == "auto":
        return LLMProviderFactory.create_from_env()
    return LLMProviderFactory.create(provider, model=model, **kwargs)
