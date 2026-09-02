class AIError(Exception):
    """Base exception for ki-core."""


class AuthError(AIError):
    pass


class RateLimitError(AIError):
    pass


class TimeoutError(AIError):
    pass


class ProviderError(AIError):
    pass


class ValidationError(AIError):
    pass
