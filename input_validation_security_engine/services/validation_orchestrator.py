from ..models.request_models import DocumentValidationInput, DocumentValidationRequest
from ..models.response_models import (
    DocumentValidationResult,
    EligibilityPreCheck,
    ValidationIssue,
    ValidationResponse,
)
from ..utils.logger import get_logger
from .document_type_service import DocumentTypeService
from .eligibility_prevalidation_service import EligibilityPreValidationService
from .metadata_validation_service import MetadataValidationService
from .ocr_input_service import OCRInputService
from .registry_client import RegistryClient, RegistryUnavailableError
from .required_document_service import RequiredDocumentService

logger = get_logger(__name__)


class ValidationOrchestrator:
    """Coordinates document-type, metadata, OCR, required-document, and
    eligibility pre-checks into a single standardized ValidationResponse.

    Required-document and eligibility pre-checks are driven by whichever
    `service_id` the caller supplies, resolved against the Official Service
    Registry - so this orchestrator never branches on a specific service.
    If the registry is unreachable, service-specific pre-checks degrade
    gracefully to a warning rather than failing the whole request, since
    per Phase A every microservice must keep running independently.
    """

    def __init__(
        self,
        document_type_service: DocumentTypeService | None = None,
        metadata_validation_service: MetadataValidationService | None = None,
        ocr_input_service: OCRInputService | None = None,
        required_document_service: RequiredDocumentService | None = None,
        eligibility_prevalidation_service: EligibilityPreValidationService | None = None,
        registry_client: RegistryClient | None = None,
    ) -> None:
        self.document_type_service = document_type_service or DocumentTypeService()
        self.metadata_validation_service = metadata_validation_service or MetadataValidationService()
        self.ocr_input_service = ocr_input_service or OCRInputService()
        self.registry_client = registry_client or RegistryClient()
        self.required_document_service = required_document_service or RequiredDocumentService(self.registry_client)
        self.eligibility_prevalidation_service = (
            eligibility_prevalidation_service or EligibilityPreValidationService(self.registry_client)
        )

    def _validate_document(self, document: DocumentValidationInput) -> DocumentValidationResult:
        all_issues: list[ValidationIssue] = []

        type_valid, type_issues = self.document_type_service.validate(document.type)
        all_issues.extend(type_issues)

        metadata_valid, metadata_issues = self.metadata_validation_service.validate(document.metadata)
        all_issues.extend(metadata_issues)

        ocr_valid, ocr_issues = self.ocr_input_service.validate(document.text)
        all_issues.extend(ocr_issues)

        is_valid = type_valid and metadata_valid and ocr_valid

        return DocumentValidationResult(
            type=document.type,
            is_supported_type=type_valid,
            metadata_valid=metadata_valid,
            ocr_valid=ocr_valid,
            is_valid=is_valid,
            issues=all_issues,
        )

    def _run_service_checks(
        self, service_id: str, submitted_types: set[str], applicant_context: dict
    ) -> tuple[list[str], EligibilityPreCheck | None, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []

        try:
            if not self.registry_client.service_exists(service_id):
                issues.append(
                    ValidationIssue(
                        code="UNKNOWN_SERVICE",
                        message=(
                            f"'{service_id}' is not a recognized service in the Official Service "
                            "Registry. Required-document and eligibility pre-checks were skipped."
                        ),
                        severity="warning",
                    )
                )
                return [], None, issues
        except RegistryUnavailableError as exc:
            logger.warning("Official Service Registry unreachable while checking service_id=%s: %s", service_id, exc)
            issues.append(
                ValidationIssue(
                    code="REGISTRY_UNAVAILABLE",
                    message=(
                        "The Official Service Registry could not be reached, so required-document "
                        "and eligibility pre-checks were skipped for this request."
                    ),
                    severity="warning",
                )
            )
            return [], None, issues

        try:
            missing_required_documents = self.required_document_service.missing_documents(
                service_id, submitted_types
            )
        except RegistryUnavailableError as exc:
            logger.warning("Registry unavailable fetching missing documents for service_id=%s: %s", service_id, exc)
            missing_required_documents = []
            issues.append(
                ValidationIssue(
                    code="REGISTRY_UNAVAILABLE",
                    message="The Official Service Registry could not be reached; required-document check skipped.",
                    severity="warning",
                )
            )

        if missing_required_documents:
            issues.append(
                ValidationIssue(
                    code="MISSING_REQUIRED_DOCUMENTS",
                    message=(
                        f"Missing required documents for '{service_id}': "
                        f"{', '.join(missing_required_documents)}."
                    ),
                    severity="error",
                )
            )

        try:
            eligibility_pre_check = self.eligibility_prevalidation_service.check(service_id, applicant_context)
        except RegistryUnavailableError as exc:
            logger.warning("Registry unavailable checking eligibility for service_id=%s: %s", service_id, exc)
            eligibility_pre_check = None
            issues.append(
                ValidationIssue(
                    code="REGISTRY_UNAVAILABLE",
                    message="The Official Service Registry could not be reached; eligibility pre-check skipped.",
                    severity="warning",
                )
            )

        return missing_required_documents, eligibility_pre_check, issues

    def validate(self, request: DocumentValidationRequest) -> ValidationResponse:
        document_results = [self._validate_document(document) for document in request.documents]
        submitted_types = {document.type for document in request.documents}

        issues_summary: list[ValidationIssue] = []
        missing_required_documents: list[str] = []
        eligibility_pre_check: EligibilityPreCheck | None = None

        if request.service_id is not None:
            missing_required_documents, eligibility_pre_check, service_issues = self._run_service_checks(
                request.service_id, submitted_types, request.resolved_applicant_context()
            )
            issues_summary.extend(service_issues)

        for result in document_results:
            issues_summary.extend(result.issues)

        has_blocking_document_errors = any(not result.is_valid for result in document_results)
        has_missing_documents = bool(missing_required_documents)
        overall_valid = not has_blocking_document_errors and not has_missing_documents

        needs_manual_review = eligibility_pre_check is not None and eligibility_pre_check.is_eligible is False

        if not overall_valid:
            status = "invalid"
        elif needs_manual_review:
            status = "manual_review"
        else:
            status = "valid"

        logger.info(
            "Validated applicant_id=%s status=%s documents=%d missing=%d",
            request.applicant_id,
            status,
            len(document_results),
            len(missing_required_documents),
        )

        return ValidationResponse(
            status=status,
            applicant_id=request.applicant_id,
            overall_valid=overall_valid,
            documents=document_results,
            missing_required_documents=missing_required_documents,
            eligibility_pre_check=eligibility_pre_check,
            issues_summary=issues_summary,
        )
