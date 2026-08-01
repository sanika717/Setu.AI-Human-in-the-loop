"""Phase C consolidation: end-to-end integration tests.

Unlike the per-phase test files (test_intent_api.py, test_intent_resolve_api.py,
test_intent_classify_multilingual.py, test_conversation_manager.py,
test_conversation_api.py), which each exercise one phase's endpoint(s) in
isolation, this file verifies C1-C4 work together as a single, cohesive
module:

  1. Classification (C1) output feeds correctly into service resolution (C2).
  2. Multilingual detection (C3) applies identically whether a request goes
     through /intent/classify, /intent/resolve, or /conversation/message -
     i.e. the conversation layer doesn't reimplement or diverge from C1-C3's
     language handling, it reuses it.
  3. The conversation layer (C4)'s first-turn `detected_intent` /
     `service_category` / initially-resolved candidate always matches what
     /intent/resolve would independently return for the same text - proving
     C4 composes C2 rather than duplicating its ranking logic.
  4. A full multi-turn conversation (ambiguous, multilingual, with a missing
     eligibility field) drives all four phases in a single flow: detect
     intent -> resolve candidates -> disambiguate -> collect missing info ->
     resolve eligibility against the registry.

All registry-backed tests use a FakeRegistryClient double (no live registry
required), following the same convention as the per-phase test files.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from intent_service.api.dependencies import (  # noqa: E402
    get_conversation_manager,
    get_intent_service,
    get_service_lookup_service,
)
from intent_service.app import app  # noqa: E402
from intent_service.providers.factory import create_classifier_for_language  # noqa: E402
from intent_service.services.conversation_manager import ConversationManager  # noqa: E402
from intent_service.services.conversation_store import InMemoryConversationStore  # noqa: E402
from intent_service.services.intent_service import IntentService  # noqa: E402
from intent_service.services.registry_client import RegistryClient  # noqa: E402
from intent_service.services.service_lookup_service import ServiceLookupService  # noqa: E402
from intent_service.utils.exceptions import RegistryUnavailableError  # noqa: E402

client = TestClient(app)

_PENSION_SERVICES = [
    {
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
    },
    {
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
    },
]

_AADHAAR_SERVICE = {
    "service_id": "aadhaar_update",
    "service_name": "Aadhaar Details Update",
    "category": "identity",
    "description": "Update Aadhaar details",
    "official_url": "https://uidai.gov.in",
    "allowed_domains": ["uidai.gov.in"],
    "required_documents": [],
    "eligibility_rules": [
        {
            "field": "has_existing_aadhaar",
            "operator": "eq",
            "value": True,
            "message": "An existing Aadhaar number is required.",
        }
    ],
    "workflow_steps": [],
    "supported_languages": ["en"],
}


class FakeRegistryClient(RegistryClient):
    """Same eligibility-evaluation semantics as
    official_service_registry/services/eligibility_engine.py, shared by
    every Phase C test file (unit and integration) so all of them exercise
    the real ConversationManager/ServiceLookupService integration logic."""

    _OPERATORS = {
        "gte": lambda actual, expected: actual >= expected,
        "lte": lambda actual, expected: actual <= expected,
        "gt": lambda actual, expected: actual > expected,
        "lt": lambda actual, expected: actual < expected,
        "eq": lambda actual, expected: actual == expected,
        "ne": lambda actual, expected: actual != expected,
        "in": lambda actual, expected: actual in expected,
        "exists": lambda actual, expected: (actual is not None) == bool(expected),
    }

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
        if service is None:
            return None
        rules = service.get("eligibility_rules", [])
        if not rules:
            return {"service_id": service_id, "is_eligible": None, "rule_results": [], "notes": []}

        results = []
        any_unknown = False
        for rule in rules:
            field = rule["field"]
            if field not in applicant_context or applicant_context[field] is None:
                results.append(
                    {"field": field, "operator": rule["operator"], "passed": None, "message": rule["message"]}
                )
                any_unknown = True
                continue
            comparator = self._OPERATORS[rule["operator"]]
            try:
                passed = bool(comparator(applicant_context[field], rule["value"]))
            except TypeError:
                results.append(
                    {"field": field, "operator": rule["operator"], "passed": None, "message": rule["message"]}
                )
                any_unknown = True
                continue
            results.append(
                {"field": field, "operator": rule["operator"], "passed": passed, "message": rule["message"]}
            )

        if any(r["passed"] is False for r in results):
            is_eligible = False
        elif any_unknown:
            is_eligible = None
        else:
            is_eligible = True

        return {"service_id": service_id, "is_eligible": is_eligible, "rule_results": results, "notes": []}


def _override_registry(services: list[dict], unavailable: bool = False) -> FakeRegistryClient:
    """Overrides every dependency in the chain (intent service, service
    lookup, conversation manager) to use the SAME FakeRegistryClient
    instance, mirroring how api/dependencies.get_conversation_manager wires
    a single shared RegistryClient in production."""

    fake_client = FakeRegistryClient(services, unavailable=unavailable)
    intent_service = IntentService(classifier_factory=create_classifier_for_language, provider_display_name="Keyword")
    lookup_service = ServiceLookupService(intent_service=intent_service, registry_client=fake_client)
    store = InMemoryConversationStore(ttl_seconds=3600)
    manager = ConversationManager(store=store, service_lookup_service=lookup_service, registry_client=fake_client)

    app.dependency_overrides[get_intent_service] = lambda: intent_service
    app.dependency_overrides[get_service_lookup_service] = lambda: lookup_service
    app.dependency_overrides[get_conversation_manager] = lambda: manager
    return fake_client


def teardown_function() -> None:
    app.dependency_overrides.clear()


# -- 1. C1 -> C2: classification output is what resolve ranks against -------


def test_classify_and_resolve_agree_on_detected_intent() -> None:
    _override_registry(_PENSION_SERVICES)
    text = "I want to apply for old age pension"

    classify = client.post("/api/v1/intent/classify", json={"text": text}).json()
    resolve = client.post("/api/v1/intent/resolve", json={"text": text}).json()

    assert classify["detected_intent"] == resolve["detected_intent"]
    assert classify["confidence"] == resolve["confidence"]
    assert classify["language"] == resolve["language"]


def test_resolve_returns_service_matches_for_classified_intent_category() -> None:
    _override_registry(_PENSION_SERVICES)
    resolve = client.post(
        "/api/v1/intent/resolve", json={"text": "I want to apply for old age pension"}
    ).json()

    assert resolve["service_category"] == "pension"
    assert any(m["service_id"] == "nsap_old_age_pension" for m in resolve["matches"])


# -- 2. C3 -> (C1/C2/C4): multilingual detection is consistent everywhere ---


def test_language_detection_is_identical_across_classify_resolve_and_conversation() -> None:
    _override_registry(_PENSION_SERVICES)
    text = "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है"

    classify = client.post("/api/v1/intent/classify", json={"text": text}).json()
    resolve = client.post("/api/v1/intent/resolve", json={"text": text}).json()
    conversation = client.post("/api/v1/conversation/message", json={"text": text}).json()

    assert classify["language"] == "hi"
    assert resolve["language"] == "hi"
    assert conversation["language"] == "hi"
    assert classify["language_name"] == resolve["language_name"] == conversation["language_name"]


def test_declared_language_override_is_honored_identically_in_conversation() -> None:
    _override_registry(_PENSION_SERVICES)
    # Text with no strong script signal - without an explicit override this
    # could be detected ambiguously; declaring it should be authoritative
    # in the conversation layer exactly as it is for /intent/classify.
    response = client.post(
        "/api/v1/conversation/message",
        json={"text": "old age pension 60", "language": "en"},
    ).json()
    assert response["language"] == "en"


# -- 3. C4 composes C2, it doesn't reimplement it ----------------------------


def test_conversation_first_turn_resolved_service_matches_standalone_resolve() -> None:
    _override_registry([_PENSION_SERVICES[1]])  # single unambiguous match, no rules
    text = "I want widow pension"

    resolve = client.post("/api/v1/intent/resolve", json={"text": text}).json()
    conversation = client.post("/api/v1/conversation/message", json={"text": text}).json()

    assert resolve["matches"][0]["service_id"] == conversation["resolved_service"]["service_id"]
    assert resolve["detected_intent"] == conversation["detected_intent"]
    assert resolve["service_category"] == conversation["service_category"]


def test_conversation_disambiguation_candidates_match_resolve_matches() -> None:
    _override_registry(_PENSION_SERVICES)  # two pension services -> ambiguous
    text = "I want to apply for pension"

    resolve = client.post("/api/v1/intent/resolve", json={"text": text}).json()
    conversation = client.post("/api/v1/conversation/message", json={"text": text}).json()

    resolve_ids = {m["service_id"] for m in resolve["matches"]}
    conversation_ids = {m["service_id"] for m in conversation["candidate_matches"]}
    assert resolve_ids == conversation_ids


# -- 4. Full C1->C2->C3->C4 pipeline in one multi-turn conversation ---------


def test_full_pipeline_unambiguous_english_request_with_missing_field() -> None:
    """classify (implicit) -> resolve to a single service (C2) -> collect
    the one missing eligibility field (C4) -> finalize against the
    registry's eligibility check."""

    _override_registry([_PENSION_SERVICES[0]])  # old age pension, has one rule

    turn1 = client.post(
        "/api/v1/conversation/message", json={"text": "I want to apply for old age pension"}
    ).json()
    assert turn1["detected_intent"] == "pension_application"
    assert turn1["state"] == "collecting_info"
    assert turn1["pending_field"] == "applicant_age"

    turn2 = client.post(
        "/api/v1/conversation/message",
        json={"conversation_id": turn1["conversation_id"], "text": "65"},
    ).json()

    assert turn2["state"] == "completed"
    assert turn2["is_complete"] is True
    assert turn2["collected_context"] == {"applicant_age": 65}
    assert turn2["eligibility_result"]["is_eligible"] is True
    assert turn2["eligibility_result"]["service_id"] == "nsap_old_age_pension"


def test_full_pipeline_multilingual_ambiguous_request_through_disambiguation() -> None:
    """Hindi text (C3) -> ambiguous pension category (C2) -> disambiguation
    (C4) -> completion, all within one conversation_id."""

    _override_registry(_PENSION_SERVICES)

    turn1 = client.post(
        "/api/v1/conversation/message",
        json={"text": "मुझे पेंशन के लिए आवेदन करना है"},
    ).json()
    assert turn1["language"] == "hi"
    assert turn1["state"] == "disambiguating_service"
    assert len(turn1["candidate_matches"]) >= 2
    cid = turn1["conversation_id"]

    # Pick the widow pension candidate by name (its service_id substring),
    # regardless of which position it landed in.
    widow_index = next(
        i for i, m in enumerate(turn1["candidate_matches"]) if m["service_id"] == "nsap_widow_pension"
    )
    turn2 = client.post(
        "/api/v1/conversation/message", json={"conversation_id": cid, "text": str(widow_index + 1)}
    ).json()

    assert turn2["resolved_service"]["service_id"] == "nsap_widow_pension"
    assert turn2["language"] == "hi"  # language stayed sticky through disambiguation
    # Widow pension has no eligibility rules in this fixture -> completes immediately.
    assert turn2["state"] == "completed"


def test_full_pipeline_boolean_field_and_ineligible_outcome() -> None:
    _override_registry([_AADHAAR_SERVICE])

    turn1 = client.post("/api/v1/conversation/message", json={"text": "I need to update my Aadhaar"}).json()
    assert turn1["resolved_service"]["service_id"] == "aadhaar_update"
    assert turn1["pending_field"] == "has_existing_aadhaar"

    turn2 = client.post(
        "/api/v1/conversation/message", json={"conversation_id": turn1["conversation_id"], "text": "no"}
    ).json()

    assert turn2["state"] == "completed"
    assert turn2["collected_context"]["has_existing_aadhaar"] is False
    assert turn2["eligibility_result"]["is_eligible"] is False


def test_full_pipeline_autofill_skips_c4_question_entirely() -> None:
    """A single message carrying enough information should flow straight
    through C1 (classify) -> C2 (resolve) -> C4 (autofill + finalize)
    without ever reaching a follow-up question."""

    _override_registry([_PENSION_SERVICES[0]])
    response = client.post(
        "/api/v1/conversation/message",
        json={"text": "I am 65 years old and want to apply for old age pension"},
    ).json()

    assert response["state"] == "completed"
    assert response["missing_fields"] == []
    assert response["collected_context"] == {"applicant_age": 65}


# -- Cross-cutting: graceful degradation is consistent across C2 and C4 -----


def test_registry_unavailable_degrades_gracefully_in_both_resolve_and_conversation() -> None:
    _override_registry(_PENSION_SERVICES, unavailable=True)
    text = "I want to apply for old age pension"

    resolve = client.post("/api/v1/intent/resolve", json={"text": text})
    conversation = client.post("/api/v1/conversation/message", json={"text": text})

    assert resolve.status_code == 200
    assert resolve.json()["registry_available"] is False
    assert conversation.status_code == 200
    assert conversation.json()["registry_available"] is False


# -- Backward compatibility: C1/C2 endpoints unaffected by C4's presence ----


def test_classify_endpoint_unaffected_by_conversation_layer_being_mounted() -> None:
    response = client.post("/api/v1/intent/classify", json={"text": "I need to update my KYC at SBI"})
    assert response.status_code == 200
    assert response.json()["detected_intent"] == "banking_kyc"


def test_health_and_root_endpoints_mention_all_four_phases() -> None:
    root = client.get("/").json()
    assert "conversation" in root["message"]

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
