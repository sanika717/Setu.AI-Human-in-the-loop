from input_validation_security_engine.models.request_models import DocumentMetadata
from input_validation_security_engine.services.document_type_service import DocumentTypeService
from input_validation_security_engine.services.eligibility_prevalidation_service import (
    EligibilityPreValidationService,
)
from input_validation_security_engine.services.metadata_validation_service import MetadataValidationService
from input_validation_security_engine.services.ocr_input_service import OCRInputService
from input_validation_security_engine.services.registry_client import RegistryUnavailableError
from input_validation_security_engine.services.required_document_service import RequiredDocumentService


class FakeRegistryClient:
    """In-memory stand-in for RegistryClient so these are pure unit tests -
    no live official_service_registry process required. Mirrors a slice of
    official_service_registry/data/services.json for two services.
    """

    _SERVICES = {
        "nsap_old_age_pension": {
            "required_documents": [
                "aadhaar",
                "address_proof",
                "bank_passbook",
                "passport_photo",
                "income_certificate",
                "age_proof",
            ],
            "min_age": 60,
        },
        "nsap_widow_pension": {
            "required_documents": [
                "aadhaar",
                "address_proof",
                "bank_passbook",
                "passport_photo",
                "income_certificate",
                "death_certificate",
            ],
            "min_age": None,
        },
    }

    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable

    def service_exists(self, service_id: str) -> bool:
        if self.unavailable:
            raise RegistryUnavailableError("simulated outage")
        return service_id in self._SERVICES

    def missing_documents(self, service_id: str, submitted_types: list[str]) -> list[str]:
        if self.unavailable:
            raise RegistryUnavailableError("simulated outage")
        service = self._SERVICES.get(service_id)
        if service is None:
            return []
        return sorted(set(service["required_documents"]) - set(submitted_types))

    def check_eligibility(self, service_id, applicant_context):
        if self.unavailable:
            raise RegistryUnavailableError("simulated outage")
        service = self._SERVICES.get(service_id)
        if service is None:
            return None
        min_age = service["min_age"]
        if min_age is None:
            return {"service_id": service_id, "is_eligible": None, "rule_results": [], "notes": []}

        applicant_age = applicant_context.get("applicant_age")
        if applicant_age is None:
            return {
                "service_id": service_id,
                "is_eligible": None,
                "rule_results": [
                    {"field": "applicant_age", "operator": "gte", "passed": None, "message": "applicant_age missing"}
                ],
                "notes": ["applicant_age was not supplied; eligibility could not be pre-checked."],
            }

        passed = applicant_age >= min_age
        return {
            "service_id": service_id,
            "is_eligible": passed,
            "rule_results": [
                {
                    "field": "applicant_age",
                    "operator": "gte",
                    "passed": passed,
                    "message": f"Applicant must be at least {min_age} years old.",
                }
            ],
            "notes": [] if passed else [f"Applicant age {applicant_age} is below the minimum required age of {min_age}."],
        }


def test_document_type_service_accepts_known_type() -> None:
    is_valid, issues = DocumentTypeService().validate("aadhaar")
    assert is_valid is True
    assert issues == []


def test_document_type_service_rejects_unknown_type() -> None:
    is_valid, issues = DocumentTypeService().validate("voter_id")
    assert is_valid is False
    assert issues[0].code == "UNSUPPORTED_DOCUMENT_TYPE"


def test_metadata_service_flags_missing_metadata_as_warning_only() -> None:
    is_valid, issues = MetadataValidationService().validate(None)
    assert is_valid is True
    assert issues[0].code == "METADATA_NOT_PROVIDED"
    assert issues[0].severity == "warning"


def test_metadata_service_rejects_oversized_file() -> None:
    metadata = DocumentMetadata(
        file_name="big.pdf", mime_type="application/pdf", size_bytes=10 * 1024 * 1024, page_count=1
    )
    is_valid, issues = MetadataValidationService().validate(metadata)
    assert is_valid is False
    assert any(issue.code == "FILE_TOO_LARGE" for issue in issues)


def test_ocr_service_rejects_empty_text() -> None:
    is_valid, issues = OCRInputService().validate("")
    assert is_valid is False
    assert issues[0].code == "OCR_TEXT_EMPTY"


def test_ocr_service_flags_low_alnum_ratio_as_warning() -> None:
    is_valid, issues = OCRInputService().validate("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    assert is_valid is True
    assert any(issue.code == "OCR_TEXT_LOW_QUALITY" for issue in issues)


def test_required_document_service_reports_missing_docs() -> None:
    service = RequiredDocumentService(FakeRegistryClient())
    missing = service.missing_documents("nsap_widow_pension", {"aadhaar"})
    assert "death_certificate" in missing
    assert "address_proof" in missing


def test_required_document_service_empty_when_all_present() -> None:
    service = RequiredDocumentService(FakeRegistryClient())
    submitted = {"aadhaar", "address_proof", "bank_passbook", "passport_photo", "income_certificate", "age_proof"}
    missing = service.missing_documents("nsap_old_age_pension", submitted)
    assert missing == []


def test_eligibility_service_flags_underage_applicant() -> None:
    service = EligibilityPreValidationService(FakeRegistryClient())
    result = service.check("nsap_old_age_pension", {"applicant_age": 40})
    assert result.is_eligible is False
    assert result.rule_results[0].passed is False


def test_eligibility_service_none_when_service_has_no_age_gate() -> None:
    service = EligibilityPreValidationService(FakeRegistryClient())
    result = service.check("nsap_widow_pension", {"applicant_age": 30})
    assert result.is_eligible is None
    assert result.rule_results == []


def test_required_document_service_raises_when_registry_unavailable() -> None:
    service = RequiredDocumentService(FakeRegistryClient(unavailable=True))
    try:
        service.missing_documents("nsap_old_age_pension", {"aadhaar"})
        assert False, "expected RegistryUnavailableError"
    except RegistryUnavailableError:
        pass
