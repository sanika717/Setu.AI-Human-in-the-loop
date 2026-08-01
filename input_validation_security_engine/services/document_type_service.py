from ..models.document_types import SUPPORTED_DOCUMENT_TYPES
from ..models.response_models import ValidationIssue


class DocumentTypeService:
    """Validates that a submitted document type is part of the supported catalog."""

    def validate(self, document_type: str) -> tuple[bool, list[ValidationIssue]]:
        if document_type in SUPPORTED_DOCUMENT_TYPES:
            return True, []

        issue = ValidationIssue(
            code="UNSUPPORTED_DOCUMENT_TYPE",
            message=(
                f"'{document_type}' is not a recognized document type. "
                f"Supported types: {', '.join(sorted(SUPPORTED_DOCUMENT_TYPES))}."
            ),
            severity="error",
        )
        return False, [issue]
