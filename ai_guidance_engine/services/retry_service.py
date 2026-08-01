import asyncio
from typing import Callable, TypeVar

from ..config import settings
from ..utils.exceptions import InvalidResponseError, ProviderConfigurationError, ProviderError, RetryExhaustedError
from ..utils.logger import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


class RetryService:
    """Retries provider calls with exponential backoff.

    Retries on transient failures - `ProviderError` (network/timeout/HTTP
    failures) and `InvalidResponseError` (malformed JSON from the model,
    which can succeed on a later attempt since LLM output is stochastic).

    `ProviderConfigurationError` (a `ProviderError` subtype raised when
    required configuration such as an API key is missing) is treated as
    non-retryable and is re-raised immediately: retrying cannot fix a
    configuration problem within a single request's lifecycle, so retrying
    it would only waste time and delay the fallback response.
    """

    def __init__(
        self,
        max_retries: int | None = None,
        backoff_base_seconds: float | None = None,
        backoff_max_seconds: float | None = None,
    ) -> None:
        self.max_retries = max_retries if max_retries is not None else settings.max_retries
        self.backoff_base_seconds = (
            backoff_base_seconds if backoff_base_seconds is not None else settings.retry_backoff_base_seconds
        )
        self.backoff_max_seconds = (
            backoff_max_seconds if backoff_max_seconds is not None else settings.retry_backoff_max_seconds
        )

    def _delay_for_attempt(self, attempt: int) -> float:
        return min(self.backoff_base_seconds * (2**attempt), self.backoff_max_seconds)

    async def execute(self, operation: Callable[[], T], *, retries: int | None = None) -> T:
        attempts = retries if retries is not None else self.max_retries
        if attempts < 1:
            attempts = 1

        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                return await operation()
            except ProviderConfigurationError:
                # Non-retryable: propagate immediately so the caller can fall back.
                raise
            except (ProviderError, InvalidResponseError) as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
                delay = self._delay_for_attempt(attempt)
                logger.warning(
                    "Provider call failed (attempt %d/%d): %s. Retrying in %.2fs",
                    attempt + 1,
                    attempts,
                    exc,
                    delay,
                )
                if delay > 0:
                    await asyncio.sleep(delay)

        raise RetryExhaustedError(str(last_error or "Retry attempts exhausted"))
