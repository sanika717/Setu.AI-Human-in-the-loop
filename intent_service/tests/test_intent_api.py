import os
import sys

from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from intent_service.app import app  # noqa: E402

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_classifies_pension_intent_with_high_confidence() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "I want to apply for old age pension"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected_intent"] == "pension_application"
    assert data["confidence_level"] in ("High", "Medium")


def test_classifies_banking_kyc_intent() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "I need to update my KYC at SBI"},
    )
    data = response.json()
    assert data["detected_intent"] == "banking_kyc"


def test_classifies_identity_document_intent() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "I want to update my Aadhaar address"},
    )
    data = response.json()
    assert data["detected_intent"] == "identity_document_update"


def test_classifies_tax_services_intent() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "How do I apply for a PAN card"},
    )
    data = response.json()
    assert data["detected_intent"] == "tax_services"


def test_returns_unclassified_for_unrelated_text() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "purple elephants dance under the moonlight"},
    )
    data = response.json()
    assert data["detected_intent"] == "unclassified"
    assert data["confidence"] == 0.0


def test_alternate_intents_are_ranked_below_top_pick() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "I need help with my pension and my bank account KYC"},
    )
    data = response.json()
    assert data["detected_intent"] in ("pension_application", "banking_kyc")
    # Whichever wins, the other should show up as an alternate, not silently dropped.
    alt_ids = [alt["intent_id"] for alt in data["alternate_intents"]]
    other = "banking_kyc" if data["detected_intent"] == "pension_application" else "pension_application"
    assert other in alt_ids


def test_greeting_intent_detected() -> None:
    response = client.post("/api/v1/intent/classify", json={"text": "Hello, good morning"})
    data = response.json()
    assert data["detected_intent"] == "greeting"


def test_applicant_id_is_accepted_but_not_required() -> None:
    response = client.post(
        "/api/v1/intent/classify",
        json={"text": "I want a new passport", "applicant_id": "applicant-123"},
    )
    assert response.status_code == 200
    assert response.json()["detected_intent"] == "identity_document_update"
