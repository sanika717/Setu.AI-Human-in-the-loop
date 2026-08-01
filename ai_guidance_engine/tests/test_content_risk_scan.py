import asyncio

from ai_guidance_engine.providers.base_provider import BaseProvider
from ai_guidance_engine.services.extraction_service import ExtractionService
from ai_guidance_engine.services.risk_client import RiskEngineUnavailableError
from ai_guidance_engine.utils.exceptions import ProviderConfigurationError


class _StubProvider(BaseProvider):
    """Fails immediately (non-retryable) so extraction falls through to the
    fallback path without any real retry delay."""

    async def extract(self, prompt: str) -> dict:
        raise ProviderConfigurationError("no API key configured for this test")


class _StubRiskClientClean:
    async def content_scan(self, page_text: str) -> dict:
        return {"engine": "Risk Engine", "sensitive_fields_detected": [], "should_pause_guidance": False, "findings": []}


class _StubRiskClientFlagged:
    async def content_scan(self, page_text: str) -> dict:
        return {
            "engine": "Risk Engine",
            "sensitive_fields_detected": ["PASSWORD"],
            "should_pause_guidance": True,
            "findings": [{"code": "SENSITIVE_FIELD_DETECTED", "message": "password-like text", "severity": "error"}],
        }


class _StubRiskClientUnavailable:
    async def content_scan(self, page_text: str) -> dict:
        raise RiskEngineUnavailableError("connection refused")


def _run_extract(risk_client):
    service = ExtractionService(provider=_StubProvider(), risk_client=risk_client)
    return asyncio.run(
        service.extract("APP-1", [{"type": "aadhaar", "text": "Applicant Name: Ramesh Patil"}])
    ), service


def test_content_scan_clean_leaves_fields_untouched() -> None:
    fields, service = _run_extract(_StubRiskClientClean())
    assert fields  # fallback path still returns a manual-review field
    assert service.last_content_risk["content_risk_verified"] is True
    assert service.last_content_risk["should_pause_guidance"] is False


def test_content_scan_flagged_redacts_values_and_pauses_guidance() -> None:
    fields, service = _run_extract(_StubRiskClientFlagged())
    assert service.last_content_risk["should_pause_guidance"] is True
    assert service.last_content_risk["findings"]
    for field in fields:
        assert field["value"] is None
        assert "paused" in field["reason"].lower()


def test_content_scan_fails_open_when_risk_engine_unreachable() -> None:
    fields, service = _run_extract(_StubRiskClientUnavailable())
    assert fields  # extraction still returns a result
    assert service.last_content_risk["content_risk_verified"] is False
    assert service.last_content_risk["should_pause_guidance"] is False
