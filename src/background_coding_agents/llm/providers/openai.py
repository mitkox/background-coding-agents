"""
OpenAI GPT provider implementation.

Secondary cloud provider for LLM judge and alternative agent scenarios.
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


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI GPT API provider.

    Supports:
    - GPT-4o, GPT-4 Turbo
    - Tool/function calling
    - Streaming responses
    - JSON mode
    """

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def is_local(self) -> bool:
        return False

    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        try:
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
            logger.info(f"Initialized OpenAI provider with model {self.config.model}")
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")

    async def close(self) -> None:
        """Close the OpenAI client."""
        if self._client:
            await self._client.close()
            self._client = None

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using GPT."""
        if not self._client:
            await self.initialize()

        # Convert messages to OpenAI format
        openai_messages = self._convert_messages(messages, system_prompt)

        # Build request kwargs
        request_kwargs: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        if tools:
            request_kwargs["tools"] = [t.to_openai_format() for t in tools]

        # Make API call with retry logic
        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.chat.completions.create(**request_kwargs)
                return self._parse_response(response)
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"OpenAI API error (attempt {attempt + 1}): {e}")
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
        """Stream a response from GPT."""
        if not self._client:
            await self.initialize()

        openai_messages = self._convert_messages(messages, system_prompt)

        request_kwargs: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "stream": True,
        }

        stream = await self._client.chat.completions.create(**request_kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _convert_messages(
        self, messages: list[Message], system_prompt: str | None = None
    ) -> list[dict[str, Any]]:
        """Convert internal message format to OpenAI format."""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        for msg in messages:
            openai_msg: dict[str, Any] = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            result.append(openai_msg)

        return result

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI response to standardized format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    },
                }
                for tc in message.tool_calls
            ]

        return LLMResponse(
            content=message.content or "",
            role=MessageRole.ASSISTANT,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
            if response.usage
            else None,
            model=response.model,
            provider=self.provider_name,
            raw_response=response,
        )
