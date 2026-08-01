"""HTTP client for the Official Service Registry (`official_service_registry`).

Mirrors system_orchestrator/app/services/registry_client.py: same call
shape, same graceful-degradation contract (RegistryUnavailableError on any
transport failure, None on a 404), so a caller of either handles
registry-down the same way.
"""

from typing import Any

import httpx

from ..config import settings
from ..utils.exceptions import RegistryUnavailableError


class RegistryClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.registry_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.registry_timeout_seconds

    async def redirect_info(self, service_id: str) -> dict[str, Any] | None:
        """Returns {"service_id", "service_name", "official_url",
        "allowed_domains"} for `service_id`, or None if the registry doesn't
        know that service_id. Raises RegistryUnavailableError if the
        registry itself cannot be reached (network error, timeout, 5xx).
        """

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/v1/services/{service_id}/redirect")
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
