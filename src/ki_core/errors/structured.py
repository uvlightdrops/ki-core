"""Structured error handling for LLM operations.

Provides typed error classes with recovery hints for better user experience.
"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class RecoveryHint:
    """Suggestion for recovering from an error."""
    title: str
    description: str
    action: Optional[str] = None  # Command or action to perform
    severity: str = "info"  # info, warning, error


class KICoreError(Exception):
    """Base exception for KI Core."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        recovery_hints: Optional[List[RecoveryHint]] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.recovery_hints = recovery_hints or []
        self.original_error = original_error
        super().__init__(self.message)

    def add_hint(self, hint: RecoveryHint) -> None:
        """Add recovery hint."""
        self.recovery_hints.append(hint)

    def __str__(self) -> str:
        msg = f"[{self.error_code}] {self.message}"
        if self.recovery_hints:
            hints_str = "\n".join(f"  - {h.title}: {h.description}" for h in self.recovery_hints)
            msg += f"\n\nRecovery suggestions:\n{hints_str}"
        return msg


# LLM-specific errors

class LLMError(KICoreError):
    """Base error for LLM operations."""
    pass


class LLMTimeoutError(LLMError):
    """Timeout during LLM API call."""
    
    def __init__(self, message: str = "LLM request timed out", timeout_seconds: int = 30):
        super().__init__(
            message,
            error_code="LLM_TIMEOUT",
            recovery_hints=[
                RecoveryHint(
                    "Retry",
                    "The provider may be overloaded. Try again in a moment.",
                    action="retry",
                ),
                RecoveryHint(
                    "Check Connection",
                    "Verify your internet connection and firewall settings.",
                ),
                RecoveryHint(
                    "Increase Timeout",
                    f"Current timeout is {timeout_seconds}s. Edit config to increase it.",
                    action="edit-config",
                ),
                RecoveryHint(
                    "Use Fallback",
                    "Try a different LLM provider if configured.",
                ),
            ],
        )


class LLMAuthError(LLMError):
    """Authentication failure with LLM provider."""
    
    def __init__(self, provider: str = "unknown", message: Optional[str] = None):
        super().__init__(
            message or f"Authentication failed with {provider}",
            error_code="LLM_AUTH_ERROR",
            recovery_hints=[
                RecoveryHint(
                    "Check API Key",
                    f"Verify your {provider} API key is correct and not expired.",
                    action="verify-api-key",
                ),
                RecoveryHint(
                    "Check Permissions",
                    f"Ensure your {provider} API key has permission to use chat/completion APIs.",
                ),
                RecoveryHint(
                    "Regenerate Key",
                    f"If key is old or suspected compromised, regenerate it in {provider} dashboard.",
                    action="regenerate-key",
                ),
            ],
        )


class LLMRateLimitError(LLMError):
    """Rate limit exceeded on LLM API."""
    
    def __init__(self, provider: str = "unknown", retry_after: Optional[int] = None):
        hints = [
            RecoveryHint(
                "Wait and Retry",
                f"Rate limit exceeded. {'Wait ' + str(retry_after) + ' seconds' if retry_after else 'Wait a moment'} before retrying.",
                action="wait-and-retry",
            ),
            RecoveryHint(
                "Reduce Frequency",
                "You're making requests too quickly. Space them out more.",
            ),
            RecoveryHint(
                "Upgrade Plan",
                f"Consider upgrading your {provider} account for higher rate limits.",
                action="upgrade-plan",
            ),
        ]
        
        super().__init__(
            f"Rate limit exceeded on {provider}",
            error_code="LLM_RATE_LIMIT",
            recovery_hints=hints,
        )
        self.retry_after = retry_after


class LLMProviderError(LLMError):
    """Provider API returned an error."""
    
    def __init__(
        self,
        provider: str = "unknown",
        status_code: Optional[int] = None,
        message: Optional[str] = None,
    ):
        provider_msg = f"{provider} returned"
        if status_code:
            provider_msg += f" error {status_code}"
        provider_msg += ": " + (message or "Unknown error")

        hints = [
            RecoveryHint(
                "Check Service Status",
                f"Visit {provider}'s status page to see if service is degraded.",
                action=f"check-{provider}-status",
            ),
            RecoveryHint(
                "Try Again",
                "The error may be temporary. Try again in a few moments.",
                action="retry",
            ),
            RecoveryHint(
                "Check Logs",
                f"Review application logs for more details about the {status_code or 'error'} response.",
                action="view-logs",
            ),
        ]
        
        super().__init__(
            provider_msg,
            error_code=f"LLM_PROVIDER_ERROR_{status_code}" if status_code else "LLM_PROVIDER_ERROR",
            recovery_hints=hints,
        )
        self.status_code = status_code


class AllProvidersFailedError(LLMError):
    """All configured LLM providers failed."""
    
    def __init__(self, providers: List[str], errors: Optional[List[Exception]] = None):
        error_summary = ", ".join(providers)
        
        hints = [
            RecoveryHint(
                "Check Configuration",
                "Verify all provider settings are correct (API keys, URLs, etc).",
                action="verify-config",
            ),
            RecoveryHint(
                "Check Network",
                "Verify your internet connection and firewall aren't blocking provider access.",
            ),
            RecoveryHint(
                "Check Services",
                f"Check status pages for: {error_summary}",
            ),
            RecoveryHint(
                "Enable Local Fallback",
                "Configure Ollama as a local fallback provider that doesn't require internet.",
                action="setup-ollama",
            ),
        ]
        
        super().__init__(
            f"All LLM providers failed: {error_summary}",
            error_code="ALL_PROVIDERS_FAILED",
            recovery_hints=hints,
        )
        self.providers = providers
        self.errors = errors or []


# Context/Input errors

class ContextError(KICoreError):
    """Error building or processing context."""
    
    def __init__(self, message: str):
        super().__init__(
            message,
            error_code="CONTEXT_ERROR",
            recovery_hints=[
                RecoveryHint(
                    "Check Project",
                    "Verify project files are readable and not corrupted.",
                ),
                RecoveryHint(
                    "Check Permissions",
                    "Ensure you have read permissions for project files.",
                    action="check-permissions",
                ),
            ],
        )


class ContextTooLargeError(ContextError):
    """Project context exceeds token limit."""
    
    def __init__(self, context_tokens: int, max_tokens: int):
        super().__init__(
            f"Project context is too large: {context_tokens} tokens (max {max_tokens})"
        )
        
        self.recovery_hints = [
            RecoveryHint(
                "Exclude Files",
                "Configure .kiignore to exclude large binary files or dependencies.",
                action="edit-.kiignore",
            ),
            RecoveryHint(
                "Reduce Selection",
                "Select fewer files/directories to analyze.",
            ),
            RecoveryHint(
                "Split Context",
                "Analyze different parts of the project separately.",
            ),
            RecoveryHint(
                "Use Larger Model",
                "Switch to a model with higher token limits (e.g., GPT-4-turbo).",
                action="upgrade-model",
            ),
        ]


# Validation errors

class ValidationError(KICoreError):
    """Input validation failed."""
    pass


class ProviderConfigError(KICoreError):
    """LLM provider not properly configured."""
    
    def __init__(self, provider: str, missing_config: Optional[str] = None):
        msg = f"{provider} is not properly configured"
        if missing_config:
            msg += f" (missing: {missing_config})"
        
        super().__init__(
            msg,
            error_code="PROVIDER_CONFIG_ERROR",
            recovery_hints=[
                RecoveryHint(
                    "Configure Provider",
                    f"Set up {provider} in your ki.yaml configuration file.",
                    action=f"configure-{provider}",
                ),
                RecoveryHint(
                    "Check Environment",
                    f"Verify {provider.upper()}_API_KEY environment variable is set.",
                ),
                RecoveryHint(
                    "View Examples",
                    f"See examples/config-{provider}.yaml for configuration template.",
                    action="view-examples",
                ),
            ],
        )
