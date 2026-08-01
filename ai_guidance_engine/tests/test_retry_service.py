import asyncio

import pytest

from ai_guidance_engine.services.retry_service import RetryService
from ai_guidance_engine.utils.exceptions import (
    InvalidResponseError,
    ProviderConfigurationError,
    ProviderError,
    RetryExhaustedError,
)


def _fast_retry_service(max_retries: int = 3) -> RetryService:
    # Zero backoff keeps the test suite fast; behavior under test is the
    # retry/no-retry decision and attempt counting, not real wall-clock delay.
    return RetryService(max_retries=max_retries, backoff_base_seconds=0, backoff_max_seconds=0)


def test_retry_service_returns_result_on_eventual_success() -> None:
    service = _fast_retry_service(max_retries=3)
    calls = {"count": 0}

    async def operation() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise ProviderError("transient failure")
        return "ok"

    result = asyncio.run(service.execute(operation))
    assert result == "ok"
    assert calls["count"] == 2


def test_retry_service_exhausts_and_raises_retry_exhausted_error() -> None:
    service = _fast_retry_service(max_retries=3)
    calls = {"count": 0}

    async def operation() -> str:
        calls["count"] += 1
        raise ProviderError("always fails")

    with pytest.raises(RetryExhaustedError):
        asyncio.run(service.execute(operation))
    assert calls["count"] == 3


def test_retry_service_retries_invalid_response_error_too() -> None:
    service = _fast_retry_service(max_retries=2)
    calls = {"count": 0}

    async def operation() -> dict:
        calls["count"] += 1
        if calls["count"] < 2:
            raise InvalidResponseError("malformed json from model")
        return {"fields": []}

    result = asyncio.run(service.execute(operation))
    assert result == {"fields": []}
    assert calls["count"] == 2


def test_retry_service_does_not_retry_configuration_errors() -> None:
    service = _fast_retry_service(max_retries=3)
    calls = {"count": 0}

    async def operation() -> str:
        calls["count"] += 1
        raise ProviderConfigurationError("missing api key")

    with pytest.raises(ProviderConfigurationError):
        asyncio.run(service.execute(operation))
    # Must fail fast: exactly one attempt, no wasted retries on an
    # unfixable configuration problem.
    assert calls["count"] == 1


def test_retry_service_backoff_delay_grows_and_is_capped() -> None:
    service = RetryService(max_retries=5, backoff_base_seconds=1.0, backoff_max_seconds=3.0)
    assert service._delay_for_attempt(0) == 1.0
    assert service._delay_for_attempt(1) == 2.0
    assert service._delay_for_attempt(2) == 3.0  # would be 4.0 uncapped
    assert service._delay_for_attempt(3) == 3.0  # stays capped
