from typing import Any

import httpx

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RegistryUnavailableError(Exception):
    """Raised when the Official Service Registry cannot be reached at all."""


class RegistryClient:
    """HTTP client for the Official Service Registry (`official_service_registry`).

    Per the microservice architecture, services communicate only over HTTP -
    no shared code imports - so this is a thin wrapper around the registry's
    REST API. Every service-specific rule (required documents, eligibility
    criteria) lives in the registry's config, never in this engine.
    """

    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.registry_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.registry_timeout_seconds

    def list_services(self) -> list[dict[str, Any]]:
        try:
            response = httpx.get(f"{self.base_url}/api/v1/services", timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        response.raise_for_status()
        return response.json()

    def service_exists(self, service_id: str) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/v1/services/{service_id}", timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def missing_documents(self, service_id: str, submitted_types: list[str]) -> list[str]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/v1/services/{service_id}/missing-documents",
                json={"submitted_document_types": submitted_types},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json().get("missing_documents", [])

    def check_eligibility(self, service_id: str, applicant_context: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = httpx.post(
                f"{self.base_url}/api/v1/services/{service_id}/eligibility",
                json={"applicant_context": applicant_context},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RegistryUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
