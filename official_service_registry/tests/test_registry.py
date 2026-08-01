import os
import sys

import pytest
from fastapi.testclient import TestClient

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from official_service_registry.app import app  # noqa: E402
from official_service_registry.services.eligibility_engine import EligibilityEngine  # noqa: E402
from official_service_registry.services.repository import ServiceRepository  # noqa: E402
from official_service_registry.services.workflow_engine import WorkflowEngine  # noqa: E402

client = TestClient(app)


@pytest.fixture()
def engine() -> WorkflowEngine:
    return WorkflowEngine(repository=ServiceRepository(), eligibility_engine=EligibilityEngine())


def test_list_services_includes_seed_data(engine: WorkflowEngine) -> None:
    services = engine.list_services()
    ids = {s.service_id for s in services}
    assert "nsap_old_age_pension" in ids
    assert "aadhaar_update" in ids
    assert "sbi_kyc_update" in ids


def test_missing_documents_for_old_age_pension(engine: WorkflowEngine) -> None:
    result = engine.missing_documents("nsap_old_age_pension", ["aadhaar", "address_proof"])
    assert "age_proof" in result.missing_documents
    assert "aadhaar" not in result.missing_documents


def test_eligibility_age_gate_fails_below_minimum(engine: WorkflowEngine) -> None:
    result = engine.check_eligibility("nsap_old_age_pension", {"applicant_age": 40})
    assert result.is_eligible is False


def test_eligibility_age_gate_passes_at_minimum(engine: WorkflowEngine) -> None:
    result = engine.check_eligibility("nsap_old_age_pension", {"applicant_age": 60})
    assert result.is_eligible is True


def test_eligibility_missing_context_field_is_unknown(engine: WorkflowEngine) -> None:
    result = engine.check_eligibility("nsap_old_age_pension", {})
    assert result.is_eligible is None


def test_no_eligibility_rules_returns_none(engine: WorkflowEngine) -> None:
    result = engine.check_eligibility("nsap_widow_pension", {"applicant_age": 30})
    assert result.is_eligible is None
    assert result.rule_results == []


def test_unknown_service_returns_404() -> None:
    response = client.get("/api/v1/services/not_a_real_service")
    assert response.status_code == 404


def test_api_list_services() -> None:
    response = client.get("/api/v1/services")
    assert response.status_code == 200
    body = response.json()
    assert any(item["service_id"] == "pan_card_application" for item in body)


def test_api_redirect_info_never_points_off_official_domain() -> None:
    response = client.get("/api/v1/services/passport_application/redirect")
    assert response.status_code == 200
    body = response.json()
    assert body["official_url"] == "https://www.passportindia.gov.in"
    assert "passportindia.gov.in" in body["allowed_domains"]


def test_api_eligibility_endpoint() -> None:
    response = client.post(
        "/api/v1/services/nsap_old_age_pension/eligibility", json={"applicant_context": {"applicant_age": 70}}
    )
    assert response.status_code == 200
    assert response.json()["is_eligible"] is True


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
