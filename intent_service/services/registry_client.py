from typing import Any

import httpx

from ..config import settings
from ..utils.exceptions import RegistryUnavailableError


class RegistryClient:
    """Mirrors risk_engine/services/registry_client.py: same call shape,
    same graceful-degradation contract (RegistryUnavailableError on any
    transport failure), so a caller of either handles registry-down the
    same way.
    """

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.registry_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.registry_timeout_seconds

    async def list_services(self, category: str | None = None) -> list[dict[str, Any]]:
        """Returns every ServiceSummary dict from GET /api/v1/services,
        optionally filtered to a single `category` (e.g. "pension").
        Filtering happens client-side since the registry's list endpoint
        doesn't take a category query param - it always returns the full
        catalog, which is small (single digits of services today).

        Raises RegistryUnavailableError if the registry itself cannot be
        reached (network error, timeout, 5xx).
        """

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/v1/services")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc

        services: list[dict[str, Any]] = response.json()
        if category:
            services = [s for s in services if s.get("category") == category]
        return services

    async def get_service(self, service_id: str) -> dict[str, Any] | None:
        """Returns the full ServiceDefinition dict (including
        `eligibility_rules`) for `service_id` from GET
        /api/v1/services/{service_id} - used by Phase C4's
        ConversationManager to know which fields still need collecting.

        Returns None if the registry is reachable but doesn't know this
        service_id (a 404), since that's a caller bug, not an
        availability problem. Raises RegistryUnavailableError only when
        the registry itself can't be reached at all, same as
        `list_services`.
        """

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/v1/services/{service_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc

        return response.json()

    async def check_eligibility(self, service_id: str, applicant_context: dict[str, Any]) -> dict[str, Any] | None:
        """Calls POST /api/v1/services/{service_id}/eligibility with the
        context Phase C4's ConversationManager has collected so far.
        Returns None on a 404 (unknown service_id); raises
        RegistryUnavailableError if the registry can't be reached at all.
        """

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/services/{service_id}/eligibility",
                    json={"applicant_context": applicant_context},
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc

        return response.json()
