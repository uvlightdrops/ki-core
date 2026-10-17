"""Async OpenAI provider (true async implementation)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from ki_core.core.client import AIClient
from ki_core.core.errors import AuthError, ProviderError, TimeoutError, ValidationError
from ki_core.core.models import ChatRequest, ChatResponse, Message, Role, StreamEvent, StreamEventType

logger = logging.getLogger(__name__)


class AsyncOpenAIClient(AIClient):
    """Async client for OpenAI API using AsyncOpenAI library."""

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """Initialize async OpenAI client.
        
        Args:
            api_key: OpenAI API key
            model: Default model name (e.g., 'gpt-4o', 'gpt-4o-mini')
            base_url: Optional custom base URL for Azure or local proxies
            timeout: Request timeout in seconds
        """
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai library required. Install: pip install openai")
        
        if not api_key:
            raise AuthError("OpenAI API key is required")
        
        self.api_key = api_key
        self.default_model = model or "gpt-4o-mini"
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = timeout
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Sync wrapper - not recommended for TUI, use achat() instead."""
        raise NotImplementedError("Use achat() for non-blocking calls")

    def chat_stream(self, request: ChatRequest) -> None:
        """Sync streaming not supported - use achat_stream() instead."""
        raise NotImplementedError("Use achat_stream() for non-blocking calls")

    async def achat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request to OpenAI asynchronously (non-blocking).
        
        Args:
            request: ChatRequest with messages and parameters
            
        Returns:
            ChatResponse with generated content
            
        Raises:
            AuthError: If API key is invalid
            TimeoutError: If request exceeds timeout
            ProviderError: If API returns error
        """
        if not request.messages:
            raise ValidationError("chat request must include at least one message")

        messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in request.messages
        ]

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=request.model or self.default_model,
                    messages=messages,
                    temperature=request.temperature or 0.7,
                    stream=False,
                ),
                timeout=self.timeout,
            )

            content = response.choices[0].message.content or ""

            return ChatResponse(
                message=Message(role=Role.ASSISTANT, content=content),
                provider="openai",
                model=response.model,
            )

        except asyncio.TimeoutError:
            raise TimeoutError(f"OpenAI request timed out after {self.timeout}s")
        except Exception as e:
            error_msg = str(e)
            
            if "401" in error_msg or "Unauthorized" in error_msg:
                raise AuthError(f"OpenAI authentication failed: {error_msg}")
            elif "429" in error_msg or "rate_limit" in error_msg:
                raise ProviderError(f"OpenAI rate limited: {error_msg}")
            elif "503" in error_msg:
                raise ProviderError(f"OpenAI service unavailable: {error_msg}")
            else:
                raise ProviderError(f"OpenAI API error: {error_msg}")

    async def achat_stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Stream chat response from OpenAI asynchronously (non-blocking).
        
        Args:
            request: ChatRequest with messages and parameters
            
        Yields:
            StreamEvent chunks as they arrive
            
        Raises:
            AuthError: If API key is invalid
            TimeoutError: If request exceeds timeout
            ProviderError: If API returns error
        """
        if not request.messages:
            raise ValidationError("chat request must include at least one message")

        messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in request.messages
        ]

        try:
            stream = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=request.model or self.default_model,
                    messages=messages,
                    temperature=request.temperature or 0.7,
                    stream=True,
                ),
                timeout=self.timeout,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield StreamEvent(
                        type=StreamEventType.TOKEN,
                        text=chunk.choices[0].delta.content,
                    )

            yield StreamEvent(type=StreamEventType.DONE)

        except asyncio.TimeoutError:
            raise TimeoutError(f"OpenAI streaming request timed out after {self.timeout}s")
        except Exception as e:
            error_msg = str(e)
            
            if "401" in error_msg:
                raise AuthError(f"OpenAI authentication failed: {error_msg}")
            elif "429" in error_msg:
                raise ProviderError(f"OpenAI rate limited: {error_msg}")
            else:
                raise ProviderError(f"OpenAI streaming error: {error_msg}")
