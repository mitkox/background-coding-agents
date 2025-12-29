"""
vLLM provider implementation.

High-performance local LLM serving for production deployments.
Supports tensor parallelism, continuous batching, and PagedAttention.

Recommended models for industrial use:
- THUDM/glm-4.7: Excellent code generation and reasoning
- MiniMaxAI/MiniMax-M2.1: Strong multilingual and code capabilities

Start vLLM with:
    vllm serve THUDM/glm-4.7 --port 8000
    vllm serve MiniMaxAI/MiniMax-M2.1 --port 8000
"""

import asyncio
import json
import logging
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


class VLLMProvider(BaseLLMProvider):
    """
    vLLM provider for high-performance local inference.

    Supports:
    - Tensor parallelism across GPUs
    - Continuous batching for high throughput
    - PagedAttention for efficient memory
    - OpenAI-compatible API
    - AWQ/GPTQ quantization

    Recommended for:
    - High-throughput production deployments
    - Multi-GPU industrial servers
    - Batch processing of migrations
    """

    DEFAULT_BASE_URL = "http://localhost:8000"

    @property
    def provider_name(self) -> str:
        return "vllm"

    @property
    def is_local(self) -> bool:
        return True

    async def initialize(self) -> None:
        """Initialize connection to vLLM server."""
        try:
            import httpx

            base_url = self.config.base_url or self.DEFAULT_BASE_URL
            self._client = httpx.AsyncClient(
                base_url=base_url,
                timeout=self.config.timeout,
            )

            # Verify connection
            try:
                response = await self._client.get("/v1/models")
                if response.status_code == 200:
                    models = response.json().get("data", [])
                    logger.info(
                        f"Connected to vLLM server with models: "
                        f"{[m['id'] for m in models]}"
                    )
            except Exception as e:
                logger.warning(f"Could not verify vLLM models: {e}")

            logger.info(f"Initialized vLLM provider with model {self.config.model}")

        except ImportError:
            raise ImportError("httpx package not installed. Install with: pip install httpx")

    async def close(self) -> None:
        """Close the vLLM client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using vLLM."""
        if not self._client:
            await self.initialize()

        # vLLM uses OpenAI-compatible API
        openai_messages = self._convert_messages(messages, system_prompt)

        request_body: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        if tools:
            request_body["tools"] = [t.to_openai_format() for t in tools]

        # Add vLLM-specific options
        if "best_of" in kwargs:
            request_body["best_of"] = kwargs["best_of"]
        if "top_p" in kwargs:
            request_body["top_p"] = kwargs["top_p"]
        if "frequency_penalty" in kwargs:
            request_body["frequency_penalty"] = kwargs["frequency_penalty"]

        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.post(
                    "/v1/chat/completions", json=request_body
                )
                response.raise_for_status()
                return self._parse_response(response.json())
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"vLLM API error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise

        raise RuntimeError("Failed to generate response after retries")

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a response from vLLM."""
        if not self._client:
            await self.initialize()

        openai_messages = self._convert_messages(messages, system_prompt)

        request_body: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }

        async with self._client.stream(
            "POST", "/v1/chat/completions", json=request_body
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if data["choices"] and data["choices"][0]["delta"].get("content"):
                            yield data["choices"][0]["delta"]["content"]
                    except json.JSONDecodeError:
                        continue

    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None = None
    ) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI format (vLLM compatible)."""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            result.append({"role": msg.role.value, "content": msg.content})

        return result

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        """Parse vLLM response to standardized format."""
        choice = response["choices"][0]
        message = choice["message"]

        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = [
                {
                    "id": tc["id"],
                    "type": tc["type"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"],
                    },
                }
                for tc in message["tool_calls"]
            ]

        usage = response.get("usage", {})

        return LLMResponse(
            content=message.get("content", ""),
            role=MessageRole.ASSISTANT,
            finish_reason=choice.get("finish_reason"),
            tool_calls=tool_calls,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            model=response.get("model"),
            provider=self.provider_name,
            raw_response=response,
        )

    async def get_server_metrics(self) -> dict[str, Any]:
        """Get vLLM server metrics for monitoring."""
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get("/metrics")
            if response.status_code == 200:
                return {"metrics_available": True, "raw": response.text}
        except Exception as e:
            logger.warning(f"Could not fetch vLLM metrics: {e}")

        return {"metrics_available": False}
