"""Provider chain for automatic fallback between multiple LLM providers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from ki_core.core.client import AIClient
from ki_core.core.errors import ProviderError, TimeoutError
from ki_core.core.models import ChatRequest, ChatResponse, StreamEvent

logger = logging.getLogger(__name__)


class ProviderChain:
    """Chain of LLM providers with automatic fallback on failure.
    
    When primary provider fails, automatically tries fallback providers in order.
    Implements retry logic with exponential backoff.
    """

    def __init__(self, providers: list[AIClient], max_retries: int = 3):
        """Initialize provider chain.
        
        Args:
            providers: List of AIClient providers in priority order
            max_retries: Max retries per provider before falling back
        """
        self.providers = providers
        self.max_retries = max_retries
        self.stats = {
            "total_queries": 0,
            "provider_attempts": {},
            "fallbacks": 0,
            "failures": 0,
        }

    async def achat(self, request: ChatRequest) -> ChatResponse:
        """Query LLM with automatic fallback on failure.
        
        Args:
            request: ChatRequest with messages and parameters
            
        Returns:
            ChatResponse from first available provider
            
        Raises:
            ProviderError: If all providers fail
        """
        self.stats["total_queries"] += 1
        provider_errors = []

        for i, provider in enumerate(self.providers):
            provider_name = type(provider).__name__
            
            if provider_name not in self.stats["provider_attempts"]:
                self.stats["provider_attempts"][provider_name] = 0
            
            self.stats["provider_attempts"][provider_name] += 1
            
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Querying {provider_name} (attempt {attempt + 1}/{self.max_retries})")
                    response = await provider.achat(request)
                    logger.info(f"✓ {provider_name} succeeded")
                    return response
                    
                except TimeoutError as e:
                    logger.warning(f"Timeout from {provider_name}: {e}")
                    provider_errors.append(e)
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.info(f"Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    continue
                    
                except ProviderError as e:
                    logger.warning(f"Error from {provider_name}: {e}")
                    provider_errors.append(e)
                    break
                    
                except Exception as e:
                    logger.error(f"Unexpected error from {provider_name}: {e}")
                    provider_errors.append(e)
                    break
            
            if i < len(self.providers) - 1:
                logger.info(f"Falling back to next provider...")
                self.stats["fallbacks"] += 1

        self.stats["failures"] += 1
        provider_names = [type(p).__name__ for p in self.providers]
        raise ProviderError(
            f"All {len(self.providers)} providers exhausted: {provider_names}"
        )

    async def achat_stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Stream LLM response with automatic fallback.
        
        Args:
            request: ChatRequest with messages and parameters
            
        Yields:
            StreamEvent chunks from first available provider
            
        Raises:
            ProviderError: If all providers fail
        """
        self.stats["total_queries"] += 1
        provider_errors = []

        for i, provider in enumerate(self.providers):
            provider_name = type(provider).__name__
            
            if provider_name not in self.stats["provider_attempts"]:
                self.stats["provider_attempts"][provider_name] = 0
            
            self.stats["provider_attempts"][provider_name] += 1
            
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Streaming from {provider_name} (attempt {attempt + 1}/{self.max_retries})")
                    async for event in provider.achat_stream(request):
                        yield event
                    logger.info(f"✓ {provider_name} streaming succeeded")
                    return
                    
                except (TimeoutError, ProviderError) as e:
                    logger.warning(f"Error from {provider_name}: {e}")
                    provider_errors.append(e)
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    continue
                    
                except Exception as e:
                    logger.error(f"Unexpected error from {provider_name}: {e}")
                    provider_errors.append(e)
                    break
            
            if i < len(self.providers) - 1:
                logger.info(f"Falling back to next provider...")
                self.stats["fallbacks"] += 1

        self.stats["failures"] += 1
        provider_names = [type(p).__name__ for p in self.providers]
        raise ProviderError(
            f"All {len(self.providers)} providers exhausted: {provider_names}"
        )

    def get_stats(self) -> dict:
        """Get chain statistics.
        
        Returns:
            Dict with query/fallback/failure stats
        """
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "total_queries": 0,
            "provider_attempts": {},
            "fallbacks": 0,
            "failures": 0,
        }
