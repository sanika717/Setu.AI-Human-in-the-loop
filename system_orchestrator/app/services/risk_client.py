"""HTTP client for the Risk Engine (`risk_engine`), Phase D Security Shield.

Mirrors registry_client.py's shape: RiskEngineUnavailableError on any
transport failure, so a caller can decide how to degrade (this service
chooses to fail *open* on unreachability rather than blocking every
redirect when risk_engine happens to be down - the whitelist check inside
risk_engine already fails closed against official_service_registry, and a
second unrelated microservice being unreachable shouldn't itself become a
hard outage for every citizen redirect. This is logged loudly either way.)
"""

from typing import Any

import httpx

from ..core.config import settings


class RiskEngineUnavailableError(Exception):
    """Raised when the Risk Engine cannot be reached at all."""


class RiskClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.risk_engine_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.risk_engine_timeout_seconds

    async def redirect_check(
        self, service_id: str, target_url: str, redirect_chain: list[str] | None = None
    ) -> dict[str, Any]:
        payload = {
            "service_id": service_id,
            "target_url": target_url,
            "redirect_chain": redirect_chain or [],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/v1/risk/redirect-check", json=payload)
        except httpx.HTTPError as exc:
            raise RiskEngineUnavailableError(str(exc)) from exc
        response.raise_for_status()
        return response.json()
