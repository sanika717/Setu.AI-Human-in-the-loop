"""HTTP client for the Risk Engine (`risk_engine`), Phase D Security Shield.

Mirrors system_orchestrator/app/services/risk_client.py's shape and its
fail-open choice: if risk_engine itself is unreachable, extraction should
not become unavailable just because one unrelated microservice is down.
The redirect path (system_orchestrator) already covers HTTPS/whitelist
risk; this client covers the other risk_engine capability - scanning
AI-generated text for sensitive-field indicators (OTP/password/PIN/CVV)
before that text is ever returned to a caller.
"""

from typing import Any

import httpx

from ..config import settings


class RiskEngineUnavailableError(Exception):
    """Raised when the Risk Engine cannot be reached at all."""


class RiskClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.risk_engine_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.risk_engine_timeout_seconds

    async def content_scan(self, page_text: str) -> dict[str, Any]:
        payload = {"page_text": page_text}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/v1/risk/content-scan", json=payload)
        except httpx.HTTPError as exc:
            raise RiskEngineUnavailableError(str(exc)) from exc
        response.raise_for_status()
        return response.json()
