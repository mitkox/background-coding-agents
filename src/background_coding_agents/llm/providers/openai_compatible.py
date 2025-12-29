"""
OpenAI-compatible API provider implementation.

Generic provider for any OpenAI-compatible API endpoint, including:
- Claude Code's local LLM support
- LM Studio
- LocalAI
- text-generation-webui
- Any other OpenAI-compatible server
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


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Generic OpenAI-compatible API provider.

    Supports any server that implements the OpenAI chat completions API:
    - POST /v1/chat/completions
    - Standard message format
    - Optional tool/function calling

    This is the recommended provider for:
    - Claude Code local LLM integration
    - Custom inference servers
    - Gateway/proxy services
    - Unified API access to multiple backends
    """

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def is_local(self) -> bool:
        # Could be local or remote depending on base_url
        base_url = self.config.base_url or ""
        return any(
            host in base_url.lower()
            for host in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
        )

    async def initialize(self) -> None:
        """Initialize the OpenAI-compatible client."""
        if not self.config.base_url:
            raise ValueError(
                "base_url is required for OpenAI-compatible provider. "
                "Set it to your inference server's URL."
            )

        try:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers=self._build_headers(),
            )

            logger.info(
                f"Initialized OpenAI-compatible provider at {self.config.base_url} "
                f"with model {self.config.model}"
            )

        except ImportError:
            raise ImportError("httpx package not installed. Install with: pip install httpx")

    def _build_headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def close(self) -> None:
        """Close the client."""
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
        """Generate a response using the OpenAI-compatible API."""
        if not self._client:
            await self.initialize()

        api_messages = self._convert_messages(messages, system_prompt)

        request_body: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        # Add tools if supported (some servers may not support this)
        if tools and kwargs.get("enable_tools", True):
            request_body["tools"] = [t.to_openai_format() for t in tools]

        # Add any extra options from config
        for key, value in self.config.extra_options.items():
            if key not in request_body:
                request_body[key] = value

        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.post(
                    "/v1/chat/completions", json=request_body
                )
                response.raise_for_status()
                return self._parse_response(response.json())
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(
                        f"OpenAI-compatible API error (attempt {attempt + 1}): {e}"
                    )
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
        """Stream a response from the OpenAI-compatible API."""
        if not self._client:
            await self.initialize()

        api_messages = self._convert_messages(messages, system_prompt)

        request_body: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "messages": api_messages,
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
                        if (
                            "choices" in data
                            and data["choices"]
                            and "delta" in data["choices"][0]
                        ):
                            content = data["choices"][0]["delta"].get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue

    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None = None
    ) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI format."""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_msg: dict[str, Any] = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id
            if msg.name:
                api_msg["name"] = msg.name
            result.append(api_msg)

        return result

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-compatible response to standardized format."""
        # Handle potential variations in response format
        choices = response.get("choices", [])
        if not choices:
            return LLMResponse(
                content="",
                role=MessageRole.ASSISTANT,
                finish_reason="error",
                provider=self.provider_name,
                raw_response=response,
            )

        choice = choices[0]
        message = choice.get("message", {})

        # Extract content
        content = message.get("content", "")

        # Parse tool calls if present
        tool_calls = None
        if "tool_calls" in message and message["tool_calls"]:
            tool_calls = []
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                tool_calls.append(
                    {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": func.get("name", ""),
                            "arguments": args,
                        },
                    }
                )

        # Extract usage if available
        usage = None
        if "usage" in response:
            usage = {
                "input_tokens": response["usage"].get("prompt_tokens", 0),
                "output_tokens": response["usage"].get("completion_tokens", 0),
            }

        return LLMResponse(
            content=content,
            role=MessageRole.ASSISTANT,
            finish_reason=choice.get("finish_reason"),
            tool_calls=tool_calls,
            usage=usage,
            model=response.get("model"),
            provider=self.provider_name,
            raw_response=response,
        )

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models from the server."""
        if not self._client:
            await self.initialize()

        try:
            response = await self._client.get("/v1/models")
            if response.status_code == 200:
                return response.json().get("data", [])
        except Exception as e:
            logger.warning(f"Could not list models: {e}")

        return []
