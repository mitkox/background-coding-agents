"""
Anthropic Claude provider implementation.

Primary cloud provider for industrial manufacturing agents,
following Spotify's recommendation for Claude as the primary model.
"""

import asyncio
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


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude API provider.

    Supports:
    - Claude Opus 4.5, Sonnet 4.5
    - Tool/function calling
    - Streaming responses
    - Extended context (200K tokens)
    """

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def is_local(self) -> bool:
        return False

    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        try:
            import anthropic

            # Build client kwargs
            client_kwargs = {
                "api_key": self.config.api_key,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
            }
            
            # Only set base_url if it's explicitly provided
            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url
                logger.info(f"Using custom base URL: {self.config.base_url}")

            self._client = anthropic.AsyncAnthropic(**client_kwargs)
            logger.info(f"Initialized Anthropic provider with model {self.config.model}")
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Install with: pip install anthropic"
            )

    async def close(self) -> None:
        """Close the Anthropic client."""
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
        """Generate a response using Claude."""
        if not self._client:
            await self.initialize()

        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Build request kwargs
        request_kwargs: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": anthropic_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        if system_prompt:
            request_kwargs["system"] = system_prompt

        if tools:
            request_kwargs["tools"] = [t.to_anthropic_format() for t in tools]

        # Make API call with retry logic
        for attempt in range(self.config.max_retries):
            try:
                response = await self._client.messages.create(**request_kwargs)
                return self._parse_response(response)
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Anthropic API error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise

        # Should not reach here
        raise RuntimeError("Failed to generate response after retries")

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a response from Claude."""
        if not self._client:
            await self.initialize()

        anthropic_messages = self._convert_messages(messages)

        request_kwargs: dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": anthropic_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        if system_prompt:
            request_kwargs["system"] = system_prompt

        async with self._client.messages.stream(**request_kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert internal message format to Anthropic format."""
        result = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # System messages handled separately in Anthropic
                continue
            anthropic_msg: dict[str, Any] = {
                "role": msg.role.value,
                "content": msg.content,
            }
            result.append(anthropic_msg)
        return result

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic response to standardized format."""
        content = ""
        tool_calls = []

        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
            elif hasattr(block, "type") and block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": block.input,
                        },
                    }
                )

        return LLMResponse(
            content=content,
            role=MessageRole.ASSISTANT,
            finish_reason=response.stop_reason,
            tool_calls=tool_calls if tool_calls else None,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            model=response.model,
            provider=self.provider_name,
            raw_response=response,
        )
