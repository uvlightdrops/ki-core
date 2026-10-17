"""Structured error handling for KI Core.

Provides typed error classes with recovery hints for better user experience.
"""

from ki_core.errors.structured import (
    KICoreError,
    RecoveryHint,
    LLMError,
    LLMTimeoutError,
    LLMAuthError,
    LLMRateLimitError,
    LLMProviderError,
    AllProvidersFailedError,
    ContextError,
    ContextTooLargeError,
    ValidationError,
    ProviderConfigError,
)

__all__ = [
    "KICoreError",
    "RecoveryHint",
    "LLMError",
    "LLMTimeoutError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMProviderError",
    "AllProvidersFailedError",
    "ContextError",
    "ContextTooLargeError",
    "ValidationError",
    "ProviderConfigError",
]
