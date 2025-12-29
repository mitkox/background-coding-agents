"""
LLM Provider implementations.

Supports cloud and local LLM providers for industrial manufacturing agents.

Local providers for air-gapped environments:
- llama.cpp: Direct model execution on industrial PCs
- vLLM: High-throughput production deployments
- OpenAI-compatible: Generic API for custom servers

Recommended local models:
- GLM-4.7: Excellent for code generation and reasoning
- MiniMax-M2.1: Strong multilingual and code capabilities
"""

from background_coding_agents.llm.providers.anthropic import AnthropicProvider
from background_coding_agents.llm.providers.llama_cpp import LlamaCppProvider
from background_coding_agents.llm.providers.openai import OpenAIProvider
from background_coding_agents.llm.providers.openai_compatible import OpenAICompatibleProvider
from background_coding_agents.llm.providers.vllm import VLLMProvider

__all__ = [
    "AnthropicProvider",
    "OpenAIProvider",
    "LlamaCppProvider",
    "VLLMProvider",
    "OpenAICompatibleProvider",
]
