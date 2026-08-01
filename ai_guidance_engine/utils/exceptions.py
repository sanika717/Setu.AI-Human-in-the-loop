class AIExtractionError(Exception):
    """Base exception for extraction engine failures."""


class ProviderError(AIExtractionError):
    """Raised when a provider request fails."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is missing required configuration (e.g. an API key).

    This is a subtype of ProviderError so existing callers that catch
    ProviderError still catch it, but RetryService treats it as
    non-retryable: retrying a request that is missing an API key cannot
    succeed on a later attempt within the same request lifecycle.
    """


class InvalidResponseError(AIExtractionError):
    """Raised when the provider returns an invalid structure."""


class RetryExhaustedError(AIExtractionError):
    """Raised after retries are exhausted."""
