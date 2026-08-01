from fastapi.testclient import TestClient

from input_validation_security_engine.api.dependencies import get_validation_orchestrator
from input_validation_security_engine.app import app
from input_validation_security_engine.services.validation_orchestrator import ValidationOrchestrator
from input_validation_security_engine.tests.test_services import FakeRegistryClient

app.dependency_overrides[get_validation_orchestrator] = lambda: ValidationOrchestrator(
    registry_client=FakeRegistryClient()
)

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["engine"] == "Input Validation & Security Engine"


def test_document_types_endpoint_lists_catalog() -> None:
    response = client.get("/api/v1/document-types")
    assert response.status_code == 200
    data = response.json()
    assert "aadhaar" in data["supported_document_types"]


def test_validate_complete_application_is_valid() -> None:
    payload = {
        "applicant_id": "123",
        "service_id": "nsap_old_age_pension",
        "applicant_age": 65,
        "documents": [
            {"type": "aadhaar", "text": "Applicant Name: Ramesh Patil, Aadhaar: 1234 5678 9012"},
            {"type": "income_certificate", "text": "Service: Old Age Pension, Annual Income: Rs 45000"},
            {"type": "age_proof", "text": "Date of Birth: 12-04-1960"},
            {"type": "address_proof", "text": "Residential Address: 12 MG Road, Pune"},
            {"type": "bank_passbook", "text": "Bank: SBI, Account Number: 987654321012"},
            {"type": "passport_photo", "text": "Passport size photograph attached"},
        ],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "valid"
    assert data["overall_valid"] is True
    assert data["missing_required_documents"] == []
    assert data["eligibility_pre_check"]["is_eligible"] is True


def test_validate_missing_required_documents_is_invalid() -> None:
    payload = {
        "applicant_id": "124",
        "service_id": "nsap_old_age_pension",
        "applicant_age": 65,
        "documents": [
            {"type": "aadhaar", "text": "Applicant Name: Ramesh Patil, Aadhaar: 1234 5678 9012"},
        ],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "invalid"
    assert data["overall_valid"] is False
    assert "age_proof" in data["missing_required_documents"]
    assert "income_certificate" in data["missing_required_documents"]


def test_validate_unsupported_document_type_is_invalid() -> None:
    payload = {
        "applicant_id": "125",
        "documents": [
            {"type": "ration_card", "text": "Ration card details for household of four members"},
        ],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "invalid"
    assert data["documents"][0]["is_supported_type"] is False
    assert any(issue["code"] == "UNSUPPORTED_DOCUMENT_TYPE" for issue in data["documents"][0]["issues"])


def test_validate_empty_ocr_text_is_invalid() -> None:
    payload = {
        "applicant_id": "126",
        "documents": [{"type": "aadhaar", "text": "   "}],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["documents"][0]["ocr_valid"] is False
    assert any(issue["code"] == "OCR_TEXT_EMPTY" for issue in data["documents"][0]["issues"])


def test_validate_underage_applicant_flags_manual_review() -> None:
    payload = {
        "applicant_id": "127",
        "service_id": "nsap_old_age_pension",
        "applicant_age": 45,
        "documents": [
            {"type": "aadhaar", "text": "Applicant Name: Suresh Rao, Aadhaar: 1234 5678 9099"},
            {"type": "income_certificate", "text": "Service: Old Age Pension, Annual Income: Rs 30000"},
            {"type": "age_proof", "text": "Date of Birth: 12-04-1980"},
            {"type": "address_proof", "text": "Residential Address: 4 Church Street, Bengaluru"},
            {"type": "bank_passbook", "text": "Bank: HDFC, Account Number: 112233445566"},
            {"type": "passport_photo", "text": "Passport size photograph attached"},
        ],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "manual_review"
    assert data["overall_valid"] is True
    assert data["eligibility_pre_check"]["is_eligible"] is False


def test_validate_unknown_service_adds_warning_and_skips_checks() -> None:
    payload = {
        "applicant_id": "128",
        "service_id": "not_a_real_service",
        "documents": [{"type": "aadhaar", "text": "Applicant Name: Test User, Aadhaar: 1111 2222 3333"}],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["missing_required_documents"] == []
    assert data["eligibility_pre_check"] is None
    assert any(issue["code"] == "UNKNOWN_SERVICE" for issue in data["issues_summary"])


def test_validate_accepts_legacy_pension_type_alias() -> None:
    """Backward compatibility: callers still sending the old 'pension_type'
    field (pre-Phase B) must keep working unmodified."""
    payload = {
        "applicant_id": "131",
        "pension_type": "nsap_old_age_pension",
        "applicant_age": 65,
        "documents": [
            {"type": "aadhaar", "text": "Applicant Name: Ramesh Patil, Aadhaar: 1234 5678 9012"},
            {"type": "income_certificate", "text": "Annual Income: Rs 45000"},
            {"type": "age_proof", "text": "Date of Birth: 12-04-1960"},
            {"type": "address_proof", "text": "Residential Address: 12 MG Road, Pune"},
            {"type": "bank_passbook", "text": "Bank: SBI, Account Number: 987654321012"},
            {"type": "passport_photo", "text": "Passport size photograph attached"},
        ],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "valid"


def test_validate_metadata_mime_type_rejected() -> None:
    payload = {
        "applicant_id": "129",
        "documents": [
            {
                "type": "aadhaar",
                "text": "Applicant Name: Test User, Aadhaar: 1111 2222 3333",
                "metadata": {
                    "file_name": "aadhaar.gif",
                    "mime_type": "image/gif",
                    "size_bytes": 10240,
                    "page_count": 1,
                },
            }
        ],
    }
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["documents"][0]["metadata_valid"] is False
    assert any(issue["code"] == "UNSUPPORTED_MIME_TYPE" for issue in data["documents"][0]["issues"])


def test_validate_rejects_empty_documents_list() -> None:
    payload = {"applicant_id": "130", "documents": []}
    response = client.post("/api/v1/validate", json=payload)
    assert response.status_code == 422
