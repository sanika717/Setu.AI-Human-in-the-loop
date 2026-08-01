import asyncio
from typing import Any

import httpx
import pytest

from ai_guidance_engine.providers.azure_provider import AzureProvider
from ai_guidance_engine.providers.claude_provider import ClaudeProvider
from ai_guidance_engine.providers.gemini_provider import GeminiProvider
from ai_guidance_engine.providers.ollama_provider import OllamaProvider
from ai_guidance_engine.providers.openai_provider import OpenAIProvider
from ai_guidance_engine.utils.exceptions import InvalidResponseError, ProviderConfigurationError, ProviderError


class _FakeResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self) -> dict[str, Any]:
        return self._json_data


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient so no real network call is made."""

    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def __call__(self, *args, **kwargs) -> "_FakeAsyncClient":
        return self

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def post(self, *args, **kwargs) -> _FakeResponse:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse | None = None, error: Exception | None = None) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient(response=response, error=error))


# --- Configuration-error fast paths (no network involved at all) ---


def test_gemini_raises_configuration_error_without_api_key() -> None:
    provider = GeminiProvider()
    provider.api_key = None
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.extract("prompt"))


def test_openai_raises_configuration_error_without_api_key() -> None:
    provider = OpenAIProvider()
    provider.api_key = None
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.extract("prompt"))


def test_claude_raises_configuration_error_without_api_key() -> None:
    provider = ClaudeProvider()
    provider.api_key = None
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.extract("prompt"))


def test_azure_raises_configuration_error_without_full_config() -> None:
    provider = AzureProvider()
    provider.api_key = None
    provider.endpoint = "https://example.openai.azure.com"
    provider.deployment = "gpt-4o"
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.extract("prompt"))


# --- Successful response parsing (network faked) ---


def test_gemini_parses_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"candidates": [{"content": {"parts": [{"text": '{"fields": []}'}]}}]}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = GeminiProvider()
    provider.api_key = "test-key"
    result = asyncio.run(provider.extract("prompt"))
    assert result == {"fields": []}


def test_openai_parses_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"choices": [{"message": {"content": '{"fields": []}'}}]}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = OpenAIProvider()
    provider.api_key = "test-key"
    result = asyncio.run(provider.extract("prompt"))
    assert result == {"fields": []}


def test_claude_parses_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"content": [{"type": "text", "text": '{"fields": []}'}]}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = ClaudeProvider()
    provider.api_key = "test-key"
    result = asyncio.run(provider.extract("prompt"))
    assert result == {"fields": []}


def test_claude_strips_markdown_code_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"content": [{"type": "text", "text": '```json\n{"fields": []}\n```'}]}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = ClaudeProvider()
    provider.api_key = "test-key"
    result = asyncio.run(provider.extract("prompt"))
    assert result == {"fields": []}


def test_azure_parses_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"choices": [{"message": {"content": '{"fields": []}'}}]}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = AzureProvider()
    provider.api_key = "test-key"
    provider.endpoint = "https://example.openai.azure.com"
    provider.deployment = "gpt-4o"
    result = asyncio.run(provider.extract("prompt"))
    assert result == {"fields": []}


def test_ollama_parses_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"message": {"content": '{"fields": []}'}}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = OllamaProvider()
    result = asyncio.run(provider.extract("prompt"))
    assert result == {"fields": []}


# --- Error paths ---


def test_openai_raises_invalid_response_error_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"choices": [{"message": {"content": "not valid json"}}]}
    _patch_async_client(monkeypatch, response=_FakeResponse(body))
    provider = OpenAIProvider()
    provider.api_key = "test-key"
    with pytest.raises(InvalidResponseError):
        asyncio.run(provider.extract("prompt"))


def test_ollama_raises_provider_error_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(monkeypatch, error=httpx.ConnectError("connection refused"))
    provider = OllamaProvider()
    with pytest.raises(ProviderError):
        asyncio.run(provider.extract("prompt"))


def test_gemini_raises_provider_error_on_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(monkeypatch, response=_FakeResponse({}, status_code=500))
    provider = GeminiProvider()
    provider.api_key = "test-key"
    with pytest.raises(ProviderError):
        asyncio.run(provider.extract("prompt"))
