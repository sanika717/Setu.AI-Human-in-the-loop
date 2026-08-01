from ..config import settings
from ..models.request_models import DocumentMetadata
from ..models.response_models import ValidationIssue


class MetadataValidationService:
    """Validates file-level metadata: MIME type, size, and page count."""

    def validate(self, metadata: DocumentMetadata | None) -> tuple[bool, list[ValidationIssue]]:
        if metadata is None:
            # Metadata is optional (e.g. text-only OCR pipelines). Not having it
            # is not a hard failure, but callers should know it wasn't checked.
            return True, [
                ValidationIssue(
                    code="METADATA_NOT_PROVIDED",
                    message="No file metadata was supplied; MIME type and size were not validated.",
                    severity="warning",
                )
            ]

        issues: list[ValidationIssue] = []

        if metadata.mime_type.lower() not in {mime.lower() for mime in settings.allowed_mime_types}:
            issues.append(
                ValidationIssue(
                    code="UNSUPPORTED_MIME_TYPE",
                    message=(
                        f"MIME type '{metadata.mime_type}' is not allowed. "
                        f"Allowed types: {', '.join(settings.allowed_mime_types)}."
                    ),
                    severity="error",
                )
            )

        if metadata.size_bytes <= 0:
            issues.append(
                ValidationIssue(
                    code="EMPTY_FILE",
                    message="Uploaded file is empty (0 bytes).",
                    severity="error",
                )
            )
        elif metadata.size_bytes > settings.max_file_size_bytes:
            issues.append(
                ValidationIssue(
                    code="FILE_TOO_LARGE",
                    message=(
                        f"File size {metadata.size_bytes} bytes exceeds the "
                        f"{settings.max_file_size_bytes} byte limit."
                    ),
                    severity="error",
                )
            )

        if metadata.page_count is not None and metadata.page_count > settings.max_page_count:
            issues.append(
                ValidationIssue(
                    code="TOO_MANY_PAGES",
                    message=(
                        f"Document has {metadata.page_count} pages, exceeding the "
                        f"{settings.max_page_count} page limit."
                    ),
                    severity="warning",
                )
            )

        is_valid = not any(issue.severity == "error" for issue in issues)
        return is_valid, issues
