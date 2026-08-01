import os
import sys

import pytest
from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from intent_service.api.dependencies import get_intent_service, get_service_lookup_service  # noqa: E402
from intent_service.app import app  # noqa: E402
from intent_service.providers.factory import create_classifier_for_language  # noqa: E402
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
        "description": "Monthly pension for senior citizens below the poverty line",
        "official_url": "https://nsap.gov.in",
        "supported_languages": ["en"],
    },
    {
        "service_id": "nsap_widow_pension",
        "service_name": "NSAP Widow Pension",
        "category": "pension",
        "description": "Monthly pension for widows below the poverty line",
        "official_url": "https://nsap.gov.in",
        "supported_languages": ["en"],
    },
]


class FakeRegistryClient(RegistryClient):
    def __init__(self, fixed_response: list[dict] | None, unavailable: bool = False):
        self.fixed_response = fixed_response or []
        self.unavailable = unavailable

    async def list_services(self, category: str | None = None):
        if self.unavailable:
            raise RegistryUnavailableError("registry unreachable (test double)")
        if category:
            return [s for s in self.fixed_response if s["category"] == category]
        return self.fixed_response


def _override_with(fake_client: FakeRegistryClient):
    intent_service = IntentService(classifier_factory=create_classifier_for_language, provider_display_name="Keyword")
    app.dependency_overrides[get_service_lookup_service] = lambda: ServiceLookupService(
        intent_service=intent_service, registry_client=fake_client
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_resolve_ranks_old_age_pension_above_widow_pension() -> None:
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "I want to apply for old age pension"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected_intent"] == "pension_application"
    assert data["service_category"] == "pension"
    assert data["registry_available"] is True
    assert len(data["matches"]) == 2
    assert data["matches"][0]["service_id"] == "nsap_old_age_pension"
    assert data["matches"][0]["match_confidence"] >= data["matches"][1]["match_confidence"]


def test_resolve_respects_max_service_matches() -> None:
    many_services = _PENSION_SERVICES + [
        {
            "service_id": "nsap_disability_pension",
            "service_name": "NSAP Disability Pension",
            "category": "pension",
            "description": "Monthly pension for persons with disabilities",
            "official_url": "https://nsap.gov.in",
            "supported_languages": ["en"],
        },
        {
            "service_id": "nsap_family_benefit_pension",
            "service_name": "NSAP Family Benefit",
            "category": "pension",
            "description": "One-time benefit for a deceased primary breadwinner's family",
            "official_url": "https://nsap.gov.in",
            "supported_languages": ["en"],
        },
    ]
    _override_with(FakeRegistryClient(many_services))
    response = client.post("/api/v1/intent/resolve", json={"text": "pension application"})
    data = response.json()
    assert len(data["matches"]) <= 3  # default INTENT_MAX_SERVICE_MATCHES


def test_resolve_returns_empty_matches_for_unclassified_text() -> None:
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "purple elephants dance under the moonlight"},
    )
    data = response.json()
    assert data["detected_intent"] == "unclassified"
    assert data["matches"] == []
    assert data["service_category"] is None
    assert data["resolution_note"] != ""


def test_resolve_returns_empty_matches_for_category_less_intent() -> None:
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post("/api/v1/intent/resolve", json={"text": "Hello, good morning"})
    data = response.json()
    assert data["detected_intent"] == "greeting"
    assert data["matches"] == []
    assert data["service_category"] is None


def test_resolve_degrades_gracefully_when_registry_unreachable() -> None:
    _override_with(FakeRegistryClient(fixed_response=None, unavailable=True))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "I want to apply for old age pension"},
    )
    assert response.status_code == 200  # never crashes - Phase A independence requirement
    data = response.json()
    assert data["registry_available"] is False
    assert data["matches"] == []
    assert data["service_category"] == "pension"


def test_resolve_handles_empty_category_in_registry() -> None:
    _override_with(FakeRegistryClient([]))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "I want to apply for old age pension"},
    )
    data = response.json()
    assert data["matches"] == []
    assert "No registered services" in data["resolution_note"]


def test_resolve_falls_back_to_even_ranking_with_no_keyword_overlap() -> None:
    no_overlap_services = [
        {
            "service_id": "scheme_alpha",
            "service_name": "XYZ Scheme One",
            "category": "pension",
            "description": "",
            "official_url": "https://nsap.gov.in",
            "supported_languages": ["en"],
        },
        {
            "service_id": "scheme_beta",
            "service_name": "XYZ Scheme Two",
            "category": "pension",
            "description": "",
            "official_url": "https://nsap.gov.in",
            "supported_languages": ["en"],
        },
    ]
    _override_with(FakeRegistryClient(no_overlap_services))
    response = client.post("/api/v1/intent/resolve", json={"text": "pension"})
    data = response.json()
    assert len(data["matches"]) == 2
    assert data["matches"][0]["service_id"] in ("scheme_alpha", "scheme_beta")
    assert data["matches"][0]["match_confidence"] == data["matches"][1]["match_confidence"]
    assert "No distinguishing keywords" in data["matches"][0]["match_reason"]


# ---------------------------------------------------------------------------
# Phase C3: multilingual /intent/resolve coverage
# ---------------------------------------------------------------------------


def test_resolve_carries_language_fields_for_english_default() -> None:
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "I want to apply for old age pension"},
    )
    data = response.json()
    assert data["language"] == "en"
    assert data["language_source"] == "detected"
    assert data["language_supported"] is True
    assert data["language_detection_confidence"] == 1.0


def test_resolve_classifies_hindi_text_via_auto_detected_language() -> None:
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "hi"
    assert data["language_name"] == "Hindi"
    assert data["language_source"] == "detected"
    assert data["language_supported"] is True
    assert data["detected_intent"] == "pension_application"
    assert data["service_category"] == "pension"


def test_resolve_prefers_services_that_support_the_resolved_language() -> None:
    mixed_services = _PENSION_SERVICES + [
        {
            "service_id": "nsap_old_age_pension_hi",
            "service_name": "NSAP Old Age Pension (Hindi-ready)",
            "category": "pension",
            "description": "Monthly pension for senior citizens, guided in Hindi",
            "official_url": "https://nsap.gov.in",
            "supported_languages": ["en", "hi"],
        }
    ]
    _override_with(FakeRegistryClient(mixed_services))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है"},
    )
    data = response.json()
    assert data["language"] == "hi"
    # Every returned match must declare Hindi support - the two English-only
    # services from _PENSION_SERVICES should have been filtered out in favor
    # of the one service that actually supports the resolved language.
    assert data["matches"]
    assert all(m["service_id"] == "nsap_old_age_pension_hi" for m in data["matches"])


def test_resolve_falls_back_to_full_category_when_no_service_supports_the_language() -> None:
    # None of _PENSION_SERVICES declares Tamil support, so the language
    # filter should find zero matches and fall back to the full category
    # list rather than returning nothing.
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "எனக்கு பென்சனுக்கு விண்ணப்பிக்க வேண்டும்"},
    )
    data = response.json()
    assert data["language"] == "ta"
    assert data["language_supported"] is True
    assert data["detected_intent"] == "pension_application"
    assert len(data["matches"]) == 2  # both English-only services, as a fallback
    assert "Tamil" in data["resolution_note"]


def test_resolve_degrades_gracefully_for_unsupported_declared_language() -> None:
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "Je veux demander une pension", "language": "fr"},
    )
    assert response.status_code == 200  # never crashes - Phase A independence requirement
    data = response.json()
    assert data["language"] == "fr"
    assert data["language_supported"] is False
    assert data["detected_intent"] == "unclassified"
    assert data["matches"] == []
    assert data["service_category"] is None
    assert "fr" in data["resolution_note"]


def test_resolve_respects_a_declared_language_over_auto_detection() -> None:
    # The text is in Hindi, but the caller explicitly declares English -
    # `language` on the request must win over auto-detection.
    _override_with(FakeRegistryClient(_PENSION_SERVICES))
    response = client.post(
        "/api/v1/intent/resolve",
        json={"text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है", "language": "en"},
    )
    data = response.json()
    assert data["language"] == "en"
    assert data["language_source"] == "declared"
    assert data["language_detection_confidence"] == 1.0

