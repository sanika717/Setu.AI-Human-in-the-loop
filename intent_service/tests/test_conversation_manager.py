import os
import sys

import pytest

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from intent_service.models.conversation_models import ConversationState  # noqa: E402
from intent_service.providers.factory import create_classifier_for_language  # noqa: E402
from intent_service.services.conversation_manager import ConversationManager  # noqa: E402
from intent_service.services.conversation_store import InMemoryConversationStore  # noqa: E402
from intent_service.services.intent_service import IntentService  # noqa: E402
from intent_service.services.registry_client import RegistryClient  # noqa: E402
from intent_service.services.service_lookup_service import ServiceLookupService  # noqa: E402
from intent_service.utils.exceptions import RegistryUnavailableError  # noqa: E402

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
    {
        "service_id": "nsap_disability_pension",
        "service_name": "NSAP Disability Pension",
        "category": "pension",
        "description": "Monthly pension for persons with disabilities",
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
    """Mirrors official_service_registry/services/eligibility_engine.py's
    exact semantics so these tests exercise ConversationManager's real
    integration logic, not a simplified stand-in.
    """

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
            comparator = _OPERATORS[rule["operator"]]
            try:
                passed = bool(comparator(applicant_context[field], rule["value"]))
            except TypeError:
                results.append(
                    {"field": field, "operator": rule["operator"], "passed": None, "message": rule["message"]}
                )
                any_unknown = True
                continue
            results.append({"field": field, "operator": rule["operator"], "passed": passed, "message": rule["message"]})

        if any(r["passed"] is False for r in results):
            is_eligible = False
        elif any_unknown:
            is_eligible = None
        else:
            is_eligible = True

        return {"service_id": service_id, "is_eligible": is_eligible, "rule_results": results, "notes": []}


def _make_manager(services: list[dict], unavailable: bool = False) -> ConversationManager:
    intent_svc = IntentService(classifier_factory=create_classifier_for_language, provider_display_name="Keyword")
    fake_client = FakeRegistryClient(services, unavailable=unavailable)
    lookup = ServiceLookupService(intent_service=intent_svc, registry_client=fake_client)
    store = InMemoryConversationStore(ttl_seconds=3600)
    return ConversationManager(store=store, service_lookup_service=lookup, registry_client=fake_client)


# -- single clear match, with and without eligibility rules -----------------


@pytest.mark.asyncio
async def test_single_match_with_no_eligibility_rules_completes_immediately() -> None:
    manager = _make_manager([_PENSION_SERVICES[1]])  # widow pension only, no rules
    response = await manager.handle_message(None, "I want widow pension", None)

    assert response.state == ConversationState.COMPLETED
    assert response.is_complete is True
    assert response.resolved_service.service_id == "nsap_widow_pension"
    assert response.missing_fields == []


@pytest.mark.asyncio
async def test_single_match_with_eligibility_rule_asks_then_completes() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])  # old age pension only
    turn1 = await manager.handle_message(None, "I want old age pension", None)

    assert turn1.state == ConversationState.COLLECTING_INFO
    assert turn1.pending_field == "applicant_age"
    assert "age" in turn1.message.lower()

    turn2 = await manager.handle_message(turn1.conversation_id, "65", None)
    assert turn2.state == ConversationState.COMPLETED
    assert turn2.is_complete is True
    assert turn2.collected_context == {"applicant_age": 65}
    assert turn2.eligibility_result.is_eligible is True


@pytest.mark.asyncio
async def test_below_minimum_age_is_reported_ineligible_not_blocked() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    turn1 = await manager.handle_message(None, "I want old age pension", None)
    turn2 = await manager.handle_message(turn1.conversation_id, "45", None)

    assert turn2.state == ConversationState.COMPLETED
    assert turn2.eligibility_result.is_eligible is False


# -- autofill from the original message (requirement 4/5) -------------------


@pytest.mark.asyncio
async def test_age_mentioned_in_first_message_is_autofilled_no_question_asked() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    response = await manager.handle_message(None, "I am 65 years old and want old age pension", None)

    assert response.state == ConversationState.COMPLETED
    assert response.collected_context == {"applicant_age": 65}
    assert response.missing_fields == []


# -- disambiguation -----------------------------------------------------------


@pytest.mark.asyncio
async def test_ambiguous_pension_request_triggers_disambiguation() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    response = await manager.handle_message(None, "I want to apply for pension", None)

    assert response.state == ConversationState.DISAMBIGUATING_SERVICE
    assert len(response.candidate_matches) >= 2


@pytest.mark.asyncio
async def test_disambiguation_by_number_selects_correct_candidate() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    turn1 = await manager.handle_message(None, "I want to apply for pension", None)
    candidates = turn1.candidate_matches

    turn2 = await manager.handle_message(turn1.conversation_id, "2", None)
    assert turn2.resolved_service.service_id == candidates[1].service_id


@pytest.mark.asyncio
async def test_disambiguation_by_name_selects_correct_candidate() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    turn1 = await manager.handle_message(None, "I want to apply for pension", None)
    assert turn1.state == ConversationState.DISAMBIGUATING_SERVICE

    turn2 = await manager.handle_message(turn1.conversation_id, "disability", None)
    assert turn2.resolved_service.service_id == "nsap_disability_pension"


@pytest.mark.asyncio
async def test_disambiguation_gives_up_after_max_attempts_and_still_completes() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    turn1 = await manager.handle_message(None, "I want to apply for pension", None)
    cid = turn1.conversation_id

    response = turn1
    for _ in range(5):
        response = await manager.handle_message(cid, "umm not sure, something else entirely", None)
        if response.state != ConversationState.DISAMBIGUATING_SERVICE:
            break

    assert response.state != ConversationState.DISAMBIGUATING_SERVICE
    assert response.resolved_service is not None


# -- clarification / unclassified intent -------------------------------------


@pytest.mark.asyncio
async def test_unclassifiable_text_asks_for_clarification() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    response = await manager.handle_message(None, "asdkjfh qwoiuer", None)

    assert response.state == ConversationState.COLLECTING_INTENT
    assert response.detected_intent in (None, "unclassified")


@pytest.mark.asyncio
async def test_repeated_unclassifiable_text_eventually_needs_human_help() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    cid = None
    response = None
    for _ in range(10):
        response = await manager.handle_message(cid, "asdkjfh qwoiuer zzz", None)
        cid = response.conversation_id
        if response.state == ConversationState.NEEDS_HUMAN_HELP:
            break

    assert response.state == ConversationState.NEEDS_HUMAN_HELP


@pytest.mark.asyncio
async def test_needs_human_help_is_terminal() -> None:
    manager = _make_manager(_PENSION_SERVICES)
    cid = None
    response = None
    for _ in range(10):
        response = await manager.handle_message(cid, "asdkjfh qwoiuer zzz", None)
        cid = response.conversation_id
        if response.state == ConversationState.NEEDS_HUMAN_HELP:
            break

    follow_up = await manager.handle_message(cid, "hello again", None)
    assert follow_up.state == ConversationState.NEEDS_HUMAN_HELP


# -- boolean field parsing ----------------------------------------------------


@pytest.mark.asyncio
async def test_boolean_field_parses_yes() -> None:
    manager = _make_manager([_AADHAAR_SERVICE])
    turn1 = await manager.handle_message(None, "I need to update my Aadhaar", None)
    assert turn1.pending_field == "has_existing_aadhaar"

    turn2 = await manager.handle_message(turn1.conversation_id, "yes", None)
    assert turn2.state == ConversationState.COMPLETED
    assert turn2.collected_context == {"has_existing_aadhaar": True}
    assert turn2.eligibility_result.is_eligible is True


@pytest.mark.asyncio
async def test_boolean_field_parses_no() -> None:
    manager = _make_manager([_AADHAAR_SERVICE])
    turn1 = await manager.handle_message(None, "I need to update my Aadhaar", None)
    turn2 = await manager.handle_message(turn1.conversation_id, "no", None)

    assert turn2.collected_context == {"has_existing_aadhaar": False}
    assert turn2.eligibility_result.is_eligible is False


@pytest.mark.asyncio
async def test_unparseable_answer_is_reasked_then_skipped_after_max_attempts() -> None:
    manager = _make_manager([_AADHAAR_SERVICE])
    turn1 = await manager.handle_message(None, "I need to update my Aadhaar", None)
    cid = turn1.conversation_id

    reask = await manager.handle_message(cid, "maybe possibly who knows", None)
    assert reask.state == ConversationState.COLLECTING_INFO
    assert reask.pending_field == "has_existing_aadhaar"

    response = reask
    for _ in range(5):
        response = await manager.handle_message(cid, "still unclear", None)
        if response.state == ConversationState.COMPLETED:
            break

    assert response.state == ConversationState.COMPLETED
    assert response.collected_context["has_existing_aadhaar"] is None


# -- duplicate-question avoidance (requirement 4) -----------------------------


@pytest.mark.asyncio
async def test_already_collected_field_is_never_asked_again() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    turn1 = await manager.handle_message(None, "I am 65 and want old age pension", None)
    # No fields left to ask - conversation completed on turn 1.
    assert turn1.state == ConversationState.COMPLETED
    assert turn1.missing_fields == []


# -- conversation context persistence (requirement 1) -------------------------


@pytest.mark.asyncio
async def test_conversation_id_is_stable_across_turns() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    turn1 = await manager.handle_message(None, "old age pension", None)
    turn2 = await manager.handle_message(turn1.conversation_id, "65", None)

    assert turn1.conversation_id == turn2.conversation_id
    assert turn2.turn_count == 2


@pytest.mark.asyncio
async def test_unknown_conversation_id_starts_a_fresh_conversation() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    response = await manager.handle_message("nonexistent-id", "old age pension", None)

    assert response.conversation_id != "nonexistent-id"
    assert response.turn_count == 1


# -- multilingual: language stays sticky across short follow-up answers ------


@pytest.mark.asyncio
async def test_language_persists_across_turns_for_numeric_followup() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    turn1 = await manager.handle_message(None, "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है", None)
    assert turn1.language == "hi"

    # A bare number has no script signal at all - without session-language
    # stickiness this would wrongly flip back to "en".
    turn2 = await manager.handle_message(turn1.conversation_id, "65", None)
    assert turn2.language == "hi"
    assert turn2.state == ConversationState.COMPLETED


# -- completed conversations are terminal -------------------------------------


@pytest.mark.asyncio
async def test_completed_conversation_does_not_reopen() -> None:
    manager = _make_manager([_PENSION_SERVICES[1]])  # no rules, completes turn 1
    turn1 = await manager.handle_message(None, "widow pension", None)
    assert turn1.state == ConversationState.COMPLETED

    turn2 = await manager.handle_message(turn1.conversation_id, "widow pension again", None)
    assert turn2.state == ConversationState.COMPLETED
    assert turn2.turn_count == 2


# -- registry unavailable degrades gracefully (never hard-fails) -------------


@pytest.mark.asyncio
async def test_registry_unavailable_during_resolve_does_not_crash() -> None:
    manager = _make_manager(_PENSION_SERVICES, unavailable=True)
    response = await manager.handle_message(None, "I want old age pension", None)

    assert response.registry_available is False
    assert response.state == ConversationState.COLLECTING_INTENT


# -- get_state / reset --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_state_does_not_advance_the_conversation() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    turn1 = await manager.handle_message(None, "old age pension", None)

    state = manager.get_state(turn1.conversation_id)
    assert state.turn_count == 1
    assert state.state == ConversationState.COLLECTING_INFO


def test_get_state_returns_none_for_unknown_id() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    assert manager.get_state("nonexistent") is None


@pytest.mark.asyncio
async def test_reset_deletes_the_conversation() -> None:
    manager = _make_manager([_PENSION_SERVICES[0]])
    turn1 = await manager.handle_message(None, "old age pension", None)

    assert manager.reset(turn1.conversation_id) is True
    assert manager.get_state(turn1.conversation_id) is None
    assert manager.reset(turn1.conversation_id) is False
