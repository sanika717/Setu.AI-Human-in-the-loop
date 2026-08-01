"""HTTP client for the Intent Service (`intent_service`, Phase C1-C4).

Mirrors registry_client.py / risk_client.py's shape exactly:
IntentServiceUnavailableError on any transport failure, one client class,
config-driven base_url/timeout. system_orchestrator is the single
integration point between the frontend and intent_service (per the
approved Phase D plan) - this client forwards conversation turns verbatim
and never re-implements or re-validates intent_service's own logic. The
response body is passed straight through as a dict; system_orchestrator
does not duplicate intent_service's response schema, it just relays it
(see models/schemas.py's ConversationTurnResponse for the thin, permissive
typing used for OpenAPI docs).
"""

from typing import Any

import httpx

from ..core.config import settings


class IntentServiceUnavailableError(Exception):
    """Raised when the Intent Service cannot be reached at all."""


class IntentClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or settings.intent_service_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.intent_service_timeout_seconds

    async def send_message(
        self,
        text: str,
        conversation_id: str | None = None,
        applicant_id: str | None = None,
        language: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "text": text,
            "conversation_id": conversation_id,
            "applicant_id": applicant_id,
            "language": language,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/v1/conversation/message", json=payload)
        except httpx.HTTPError as exc:
            raise IntentServiceUnavailableError(str(exc)) from exc
        response.raise_for_status()
        return response.json()

    async def get_conversation_state(self, conversation_id: str) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/api/v1/conversation/{conversation_id}")
        except httpx.HTTPError as exc:
            raise IntentServiceUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def reset_conversation(self, conversation_id: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.delete(f"{self.base_url}/api/v1/conversation/{conversation_id}")
        except httpx.HTTPError as exc:
            raise IntentServiceUnavailableError(str(exc)) from exc
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True
