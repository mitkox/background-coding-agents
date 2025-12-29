"""
llama.cpp provider implementation.

Direct integration with llama.cpp for maximum performance on local hardware.
Supports GGUF models and GPU acceleration via CUDA, Metal, or ROCm.

Recommended models for industrial use:
- GLM-4.7: Excellent code generation and reasoning
- MiniMax-M2.1: Strong multilingual and code capabilities

Example GGUF files:
- glm-4.7.Q4_K_M.gguf
- MiniMax-M2.1.Q4_K_M.gguf
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator

from background_coding_agents.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
    Message,
    MessageRole,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class LlamaCppProvider(BaseLLMProvider):
    """
    llama.cpp provider for direct model execution.

    Supports:
    - GGUF model format
    - GPU acceleration (CUDA, Metal, ROCm)
    - Quantized models (Q4_K_M, Q5_K_M, Q8_0, etc.)
    - Extended context via RoPE scaling
    - Grammar-constrained generation

    Recommended for:
    - Air-gapped industrial environments
    - Edge deployment on industrial PCs
    - Maximum control over inference
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._llm: Any = None

    @property
    def provider_name(self) -> str:
        return "llama_cpp"

    @property
    def is_local(self) -> bool:
        return True

    async def initialize(self) -> None:
        """Initialize the llama.cpp model."""
        try:
            from llama_cpp import Llama

            # Run model loading in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self._llm = await loop.run_in_executor(
                self._executor,
                lambda: Llama(
                    model_path=self.config.model,  # Path to GGUF file
                    n_ctx=self.config.n_ctx,
                    n_gpu_layers=self.config.n_gpu_layers,
                    verbose=False,
                    chat_format="chatml",  # Standard chat format
                    **self.config.extra_options,
                ),
            )
            logger.info(
                f"Initialized llama.cpp with model {self.config.model} "
                f"(n_ctx={self.config.n_ctx}, n_gpu_layers={self.config.n_gpu_layers})"
            )
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Install with: "
                "pip install llama-cpp-python or "
                "CMAKE_ARGS='-DLLAMA_CUBLAS=on' pip install llama-cpp-python (for CUDA)"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")

    async def close(self) -> None:
        """Close the llama.cpp instance."""
        if self._llm:
            del self._llm
            self._llm = None
        self._executor.shutdown(wait=False)

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using llama.cpp."""
        if not self._llm:
            await self.initialize()

        # Convert messages to chat format
        llama_messages = self._convert_messages(messages, system_prompt)

        # Prepare generation kwargs
        gen_kwargs = {
            "messages": llama_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stop": kwargs.get("stop", ["<|im_end|>", "</s>"]),
        }

        # Add grammar for tool calling if needed
        if tools:
            gen_kwargs["grammar"] = self._create_tool_grammar(tools)

        # Run inference in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            self._executor, lambda: self._llm.create_chat_completion(**gen_kwargs)
        )

        return self._parse_response(response, tools)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a response from llama.cpp."""
        if not self._llm:
            await self.initialize()

        llama_messages = self._convert_messages(messages, system_prompt)

        gen_kwargs = {
            "messages": llama_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }

        loop = asyncio.get_event_loop()

        # Create generator in thread
        def generate():
            return self._llm.create_chat_completion(**gen_kwargs)

        stream = await loop.run_in_executor(self._executor, generate)

        for chunk in stream:
            if "choices" in chunk and chunk["choices"]:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta and delta["content"]:
                    yield delta["content"]

    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None = None
    ) -> list[dict[str, str]]:
        """Convert internal message format to llama.cpp chat format."""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            result.append({"role": msg.role.value, "content": msg.content})

        return result

    def _create_tool_grammar(self, tools: list[ToolDefinition]) -> Any:
        """Create a grammar for structured tool calling output."""
        # This is a simplified grammar for JSON tool calls
        # Production would use llama.cpp's full grammar support
        try:
            from llama_cpp import LlamaGrammar

            # Create grammar that enforces JSON output with tool structure
            grammar_str = r"""
root ::= tool-call
tool-call ::= "{" ws "\"tool\":" ws string "," ws "\"arguments\":" ws object ws "}"
object ::= "{" ws (pair ("," ws pair)*)? ws "}"
pair ::= string ":" ws value
value ::= string | number | "true" | "false" | "null" | object | array
array ::= "[" ws (value ("," ws value)*)? ws "]"
string ::= "\"" ([^"\\] | "\\" .)* "\""
number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
ws ::= [ \t\n]*
"""
            return LlamaGrammar.from_string(grammar_str)
        except Exception:
            return None

    def _parse_response(
        self, response: dict[str, Any], tools: list[ToolDefinition] | None = None
    ) -> LLMResponse:
        """Parse llama.cpp response to standardized format."""
        choice = response["choices"][0]
        content = choice["message"]["content"]

        # Try to parse tool calls from structured output
        tool_calls = None
        if tools and content.strip().startswith("{"):
            try:
                import json

                parsed = json.loads(content)
                if "tool" in parsed:
                    tool_calls = [
                        {
                            "id": "call_0",
                            "type": "function",
                            "function": {
                                "name": parsed["tool"],
                                "arguments": parsed.get("arguments", {}),
                            },
                        }
                    ]
                    content = ""  # Clear content when we have tool calls
            except Exception:
                pass

        usage = response.get("usage", {})

        return LLMResponse(
            content=content,
            role=MessageRole.ASSISTANT,
            finish_reason=choice.get("finish_reason"),
            tool_calls=tool_calls,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            model=self.config.model,
            provider=self.provider_name,
            raw_response=response,
        )

    async def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        if not self._llm:
            return {"loaded": False}

        return {
            "loaded": True,
            "model_path": self.config.model,
            "n_ctx": self.config.n_ctx,
            "n_gpu_layers": self.config.n_gpu_layers,
            "vocab_size": getattr(self._llm, "n_vocab", "unknown"),
        }
