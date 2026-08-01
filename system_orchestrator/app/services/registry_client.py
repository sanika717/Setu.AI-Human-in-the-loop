"""HTTP client for the Official Service Registry (`official_service_registry`).

Used by api/routes.py to back GET /portals and POST /portals/confirm with the
real, config-driven service catalog instead of a hardcoded fake portal list -
so adding a new government/banking service is a data change to
official_service_registry/data/services.json, never a code change here.
"""

from typing import Any

import httpx

from ..core.config import settings


class RegistryUnavailableError(Exception):
    """Raised when the Official Service Registry cannot be reached at all."""


class RegistryClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.registry_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.registry_timeout_seconds

    async def list_services(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/v1/services")
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        response.raise_for_status()
        return response.json()

    async def redirect_info(self, service_id: str) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/v1/services/{service_id}/redirect")
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
