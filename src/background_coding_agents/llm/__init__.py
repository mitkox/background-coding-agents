"""
LLM Provider System for Industrial Manufacturing Agents.

This module provides a unified interface for working with LLMs, supporting
both cloud APIs and local models for air-gapped industrial environments.

Supported Providers:
- Cloud: Anthropic Claude, OpenAI GPT
- Local: llama.cpp, vLLM, OpenAI-compatible endpoints

Recommended Local Models:
- GLM-4.7: Excellent code generation and reasoning
- MiniMax-M2.1: Strong multilingual and code capabilities

Usage:
    from background_coding_agents.llm import create_provider, LLMProviderFactory

    # Auto-detect best available provider
    provider = create_provider("auto")

    # Use vLLM with GLM-4.7
    provider = create_provider("vllm", model="THUDM/glm-4.7")

    # Use llama.cpp with MiniMax-M2.1
    provider = create_provider("llama_cpp", model="models/MiniMax-M2.1.Q4_K_M.gguf")

    # Generate response
    response = await provider.generate(messages=[...])

    # Stream response
    async for chunk in provider.stream(messages=[...]):
        print(chunk, end="")
"""

from background_coding_agents.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
    Message,
    MessageRole,
    ProviderType,
    ToolDefinition,
)
from background_coding_agents.llm.factory import (
    LLMProviderFactory,
    create_provider,
)
from background_coding_agents.llm.providers import (
    AnthropicProvider,
    LlamaCppProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    VLLMProvider,
)

__all__ = [
    # Base classes
    "BaseLLMProvider",
    "LLMConfig",
    "LLMResponse",
    "Message",
    "MessageRole",
    "ProviderType",
    "ToolDefinition",
    # Factory
    "LLMProviderFactory",
    "create_provider",
    # Providers
    "AnthropicProvider",
    "OpenAIProvider",
    "LlamaCppProvider",
    "VLLMProvider",
    "OpenAICompatibleProvider",
]
