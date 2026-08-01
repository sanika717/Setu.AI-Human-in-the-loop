"""Phase D integration tests: system_orchestrator's /api/v1/conversation/*
proxy routes to intent_service.

Follows the same pattern as the rest of this test module (test_api.py):
real ASGI requests against `app.main.app` via httpx's ASGITransport. Unlike
test_api.py's portal tests (which rely on the Official Service Registry
being unreachable in this sandbox and exercise the FALLBACK_PORTAL_LIST
path), these tests use `app.dependency_overrides` to replace
`get_intent_client` with an in-memory fake - the same technique
intent_service's own test suite uses for its RegistryClient - so they never
need a live intent_service process either.

These tests verify:
  1. A conversation message is proxied to intent_service and the response
     relayed back with the fields the frontend/portal flow needs.
  2. GET/DELETE conversation-state proxy routes behave correctly, including
     404 passthrough for an unknown conversation_id.
  3. Intent Service unavailability degrades to a 502, not a crash, and
     does not affect any other route (Phase A "every microservice runs
     independently" contract, now extended to intent_service).
  4. The existing portal-card workflow (GET /portals, POST /portals/confirm)
     is completely unaffected by this change (backward compatibility).
  5. End-to-end: a completed conversation's `resolved_service.service_id`
     is used, unmodified, as `portal_id` for the pre-existing
     POST /portals/confirm endpoint - proving no new linking model was
     needed, exactly as planned.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.api.routes import get_intent_client
from app.services.intent_client import IntentServiceUnavailableError


class FakeIntentClient:
    """In-memory stand-in for IntentClient. Simulates a two-turn
    conversation (intent detected -> one follow-up question -> completed
    with a resolved service) without needing a live intent_service process.
    """

    def __init__(self, unavailable: bool = False):
        self.unavailable = unavailable
        self._conversations: dict[str, dict] = {}

    async def send_message(self, text, conversation_id=None, applicant_id=None, language=None):
        if self.unavailable:
            raise IntentServiceUnavailableError("unreachable (test double)")

        if conversation_id is None or conversation_id not in self._conversations:
            conversation_id = conversation_id or "conv-fake-1"
            turn = {
                "engine": "Intent Service",
                "conversation_id": conversation_id,
                "state": "collecting_info",
                "turn_count": 1,
                "message": "What is your age?",
                "language": language or "en",
                "language_name": "English",
                "detected_intent": "pension_application",
                "label": "Apply for a pension",
                "confidence": 0.9,
                "service_category": "pension",
                "candidate_matches": [],
                "resolved_service": {
                    "service_id": "gov-banking-a",
                    "service_name": "Government Banking Portal A",
                    "category": "pension",
                    "description": "",
                    "official_url": "https://www.example.gov/banking-a",
                    "match_confidence": 0.9,
                    "match_reason": "keyword overlap",
                },
                "collected_context": {},
                "missing_fields": ["applicant_age"],
                "pending_field": "applicant_age",
                "eligibility_result": None,
                "is_complete": False,
                "registry_available": True,
                "notes": [],
            }
            self._conversations[conversation_id] = turn
            return turn

        # second turn: citizen answers the age question -> conversation completes
        turn = dict(self._conversations[conversation_id])
        turn.update(
            {
                "turn_count": turn["turn_count"] + 1,
                "state": "completed",
                "message": "You're eligible. Redirecting you to the official site.",
                "collected_context": {"applicant_age": 65},
                "missing_fields": [],
                "pending_field": None,
                "eligibility_result": {
                    "service_id": "gov-banking-a",
                    "is_eligible": True,
                    "rule_results": [],
                    "notes": [],
                },
                "is_complete": True,
            }
        )
        self._conversations[conversation_id] = turn
        return turn

    async def get_conversation_state(self, conversation_id):
        if self.unavailable:
            raise IntentServiceUnavailableError("unreachable (test double)")
        return self._conversations.get(conversation_id)

    async def reset_conversation(self, conversation_id):
        if self.unavailable:
            raise IntentServiceUnavailableError("unreachable (test double)")
        return self._conversations.pop(conversation_id, None) is not None


def _override_intent_client(unavailable: bool = False) -> FakeIntentClient:
    fake = FakeIntentClient(unavailable=unavailable)
    app.dependency_overrides[get_intent_client] = lambda: fake
    return fake


def teardown_function():
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_conversation_message_proxies_to_intent_service():
    _override_intent_client()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/conversation/message", json={"text": "I want to apply for old age pension"}
        )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["state"] == "collecting_info"
    assert data["detected_intent"] == "pension_application"
    assert data["pending_field"] == "applicant_age"
    assert data["conversation_id"]


@pytest.mark.asyncio
async def test_conversation_flow_reuses_existing_portal_confirm_with_resolved_service_id():
    """The key Phase D integration proof: no new linking model - the
    resolved conversation's service_id is handed straight to the
    pre-existing /portals/confirm endpoint."""

    _override_intent_client()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        turn1 = await client.post("/api/v1/conversation/message", json={"text": "old age pension"})
        conversation_id = turn1.json()["conversation_id"]

        turn2 = await client.post(
            "/api/v1/conversation/message", json={"conversation_id": conversation_id, "text": "65"}
        )
        turn2_data = turn2.json()
        assert turn2_data["state"] == "completed"
        service_id = turn2_data["resolved_service"]["service_id"]

        # Reuse the existing, unmodified portal flow - no new model/endpoint.
        confirm = await client.post(
            "/api/v1/portals/confirm",
            json={"portal_id": service_id, "permission_given": True},
        )

    assert confirm.status_code == status.HTTP_200_OK
    assert confirm.json()["portal_id"] == service_id


@pytest.mark.asyncio
async def test_get_conversation_state_returns_current_turn():
    fake = _override_intent_client()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        started = await client.post("/api/v1/conversation/message", json={"text": "old age pension"})
        conversation_id = started.json()["conversation_id"]

        response = await client.get(f"/api/v1/conversation/{conversation_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_get_conversation_state_unknown_id_returns_404():
    _override_intent_client()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/conversation/does-not-exist")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_reset_conversation_deletes_and_then_404s():
    _override_intent_client()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        started = await client.post("/api/v1/conversation/message", json={"text": "old age pension"})
        conversation_id = started.json()["conversation_id"]

        delete_response = await client.delete(f"/api/v1/conversation/{conversation_id}")
        assert delete_response.status_code == status.HTTP_200_OK
        assert delete_response.json()["deleted"] is True

        second_delete = await client.delete(f"/api/v1/conversation/{conversation_id}")

    assert second_delete.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_conversation_message_returns_502_when_intent_service_unavailable():
    _override_intent_client(unavailable=True)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/conversation/message", json={"text": "old age pension"})

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


@pytest.mark.asyncio
async def test_portal_workflow_unaffected_by_conversation_routes_being_present():
    """Backward compatibility: the pre-existing portal-card flow (no
    conversation involved at all) still works exactly as before."""

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_response = await client.get("/api/v1/portals")
        assert list_response.status_code == status.HTTP_200_OK
        portals = list_response.json()
        assert len(portals) >= 1

        confirm_response = await client.post(
            "/api/v1/portals/confirm",
            json={"portal_id": portals[0]["id"], "permission_given": True},
        )

    assert confirm_response.status_code == status.HTTP_200_OK
    assert confirm_response.json()["portal_id"] == portals[0]["id"]
