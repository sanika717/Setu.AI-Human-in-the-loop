import os
import sys

from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from intent_service.api.dependencies import get_conversation_manager  # noqa: E402
from intent_service.app import app  # noqa: E402
from intent_service.providers.factory import create_classifier_for_language  # noqa: E402
from intent_service.services.conversation_manager import ConversationManager  # noqa: E402
from intent_service.services.conversation_store import InMemoryConversationStore  # noqa: E402
from intent_service.services.intent_service import IntentService  # noqa: E402
from intent_service.services.registry_client import RegistryClient  # noqa: E402
from intent_service.services.service_lookup_service import ServiceLookupService  # noqa: E402
from intent_service.utils.exceptions import RegistryUnavailableError  # noqa: E402

client = TestClient(app)

_WIDOW_PENSION_NO_RULES = {
    "service_id": "nsap_widow_pension",
    "service_name": "NSAP Widow Pension",
    "category": "pension",
    "description": "Monthly pension for widows",
    "official_url": "https://nsap.nic.in",
    "allowed_domains": ["nsap.nic.in"],
    "required_documents": [],
    "eligibility_rules": [],
    "workflow_steps": [],
    "supported_languages": ["en", "hi"],
}

_OLD_AGE_PENSION_WITH_RULE = {
    "service_id": "nsap_old_age_pension",
    "service_name": "NSAP Old Age Pension",
    "category": "pension",
    "description": "Monthly pension for senior citizens",
    "official_url": "https://nsap.nic.in",
    "allowed_domains": ["nsap.nic.in"],
    "required_documents": [],
    "eligibility_rules": [
        {"field": "applicant_age", "operator": "gte", "value": 60, "message": "Must be at least 60."}
    ],
    "workflow_steps": [],
    "supported_languages": ["en", "hi"],
}


class FakeRegistryClient(RegistryClient):
    def __init__(self, services: list[dict], unavailable: bool = False):
        self.services = {s["service_id"]: s for s in services}
        self.unavailable = unavailable

    async def list_services(self, category: str | None = None):
        if self.unavailable:
            raise RegistryUnavailableError("unreachable (test double)")
        values = list(self.services.values())
        if category:
            values = [s for s in values if s["category"] == category]
        return [
            {
                "service_id": s["service_id"],
                "service_name": s["service_name"],
                "category": s["category"],
                "description": s["description"],
                "official_url": s["official_url"],
                "supported_languages": s["supported_languages"],
            }
            for s in values
        ]

    async def get_service(self, service_id: str):
        if self.unavailable:
            raise RegistryUnavailableError("unreachable (test double)")
        return self.services.get(service_id)

    async def check_eligibility(self, service_id: str, applicant_context: dict):
        if self.unavailable:
            raise RegistryUnavailableError("unreachable (test double)")
        service = self.services.get(service_id)
        rules = service.get("eligibility_rules", []) if service else []
        if not rules:
            return {"service_id": service_id, "is_eligible": None, "rule_results": [], "notes": []}
        results = []
        for rule in rules:
            value = applicant_context.get(rule["field"])
            passed = value is not None and value >= rule["value"]
            results.append({"field": rule["field"], "operator": rule["operator"], "passed": passed, "message": rule["message"]})
        return {
            "service_id": service_id,
            "is_eligible": all(r["passed"] for r in results),
            "rule_results": results,
            "notes": [],
        }


def _override_with(services: list[dict], unavailable: bool = False) -> None:
    intent_service = IntentService(classifier_factory=create_classifier_for_language, provider_display_name="Keyword")
    fake_client = FakeRegistryClient(services, unavailable=unavailable)
    lookup = ServiceLookupService(intent_service=intent_service, registry_client=fake_client)
    store = InMemoryConversationStore(ttl_seconds=3600)
    manager = ConversationManager(store=store, service_lookup_service=lookup, registry_client=fake_client)
    app.dependency_overrides[get_conversation_manager] = lambda: manager


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_message_without_conversation_id_starts_new_conversation() -> None:
    _override_with([_WIDOW_PENSION_NO_RULES])
    response = client.post("/api/v1/conversation/message", json={"text": "I want widow pension"})

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"]
    assert data["state"] == "completed"
    assert data["is_complete"] is True


def test_message_with_conversation_id_continues_same_conversation() -> None:
    _override_with([_OLD_AGE_PENSION_WITH_RULE])
    turn1 = client.post("/api/v1/conversation/message", json={"text": "old age pension"}).json()
    assert turn1["state"] == "collecting_info"

    turn2 = client.post(
        "/api/v1/conversation/message",
        json={"conversation_id": turn1["conversation_id"], "text": "65"},
    ).json()
    assert turn2["conversation_id"] == turn1["conversation_id"]
    assert turn2["state"] == "completed"
    assert turn2["turn_count"] == 2


def test_get_conversation_state_returns_current_state_without_advancing() -> None:
    _override_with([_OLD_AGE_PENSION_WITH_RULE])
    turn1 = client.post("/api/v1/conversation/message", json={"text": "old age pension"}).json()

    state_response = client.get(f"/api/v1/conversation/{turn1['conversation_id']}")
    assert state_response.status_code == 200
    data = state_response.json()
    assert data["turn_count"] == 1
    assert data["state"] == "collecting_info"


def test_get_conversation_state_404_for_unknown_id() -> None:
    _override_with([_OLD_AGE_PENSION_WITH_RULE])
    response = client.get("/api/v1/conversation/does-not-exist")
    assert response.status_code == 404


def test_delete_conversation_resets_it() -> None:
    _override_with([_OLD_AGE_PENSION_WITH_RULE])
    turn1 = client.post("/api/v1/conversation/message", json={"text": "old age pension"}).json()

    delete_response = client.delete(f"/api/v1/conversation/{turn1['conversation_id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    follow_up = client.get(f"/api/v1/conversation/{turn1['conversation_id']}")
    assert follow_up.status_code == 404


def test_delete_unknown_conversation_404() -> None:
    _override_with([_OLD_AGE_PENSION_WITH_RULE])
    response = client.delete("/api/v1/conversation/does-not-exist")
    assert response.status_code == 404


def test_registry_unavailable_is_reflected_in_response() -> None:
    _override_with([_OLD_AGE_PENSION_WITH_RULE], unavailable=True)
    response = client.post("/api/v1/conversation/message", json={"text": "old age pension"})

    assert response.status_code == 200
    assert response.json()["registry_available"] is False
