from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from typing import Optional

from ki_core.core.models import ChatRequest, ChatResponse, StreamEvent


class AIClient(ABC):
    """Base class for AI providers (synchronous interface)."""
    
    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request synchronously.
        
        Args:
            request: ChatRequest with messages and parameters
            
        Returns:
            ChatResponse with generated content
        """
        raise NotImplementedError

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Stream chat response synchronously.
        
        Args:
            request: ChatRequest with messages and parameters
            
        Yields:
            StreamEvent chunks as they arrive
        """
        raise NotImplementedError

    async def achat(self, request: ChatRequest) -> ChatResponse:
        """Send chat request asynchronously (non-blocking).
        
        Default implementation uses sync chat() in thread pool.
        Providers can override for true async implementations.
        
        Args:
            request: ChatRequest with messages and parameters
            
        Returns:
            ChatResponse with generated content
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.chat, request)

    async def achat_stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Stream chat response asynchronously (non-blocking).
        
        Default implementation uses sync chat_stream() in thread pool.
        Providers can override for true async implementations.
        
        Args:
            request: ChatRequest with messages and parameters
            
        Yields:
            StreamEvent chunks as they arrive
        """
        import asyncio
        loop = asyncio.get_event_loop()
        
        def sync_stream():
            return list(self.chat_stream(request))
        
        events = await loop.run_in_executor(None, sync_stream)
        for event in events:
            yield event
