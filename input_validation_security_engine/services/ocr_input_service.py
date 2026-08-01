import re

from ..config import settings
from ..models.response_models import ValidationIssue

_ALNUM_PATTERN = re.compile(r"[A-Za-z0-9]")


class OCRInputService:
    """Validates the quality of OCR-extracted text before it reaches extraction."""

    def validate(self, text: str) -> tuple[bool, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []
        stripped = text.strip()

        if not stripped:
            issues.append(
                ValidationIssue(
                    code="OCR_TEXT_EMPTY",
                    message="OCR text is empty or whitespace only.",
                    severity="error",
                )
            )
            return False, issues

        if len(stripped) < settings.min_ocr_text_length:
            issues.append(
                ValidationIssue(
                    code="OCR_TEXT_TOO_SHORT",
                    message=(
                        f"OCR text is {len(stripped)} characters, below the "
                        f"{settings.min_ocr_text_length} character minimum. OCR may have failed."
                    ),
                    severity="error",
                )
            )

        if len(stripped) > settings.max_ocr_text_length:
            issues.append(
                ValidationIssue(
                    code="OCR_TEXT_TOO_LONG",
                    message=(
                        f"OCR text is {len(stripped)} characters, above the "
                        f"{settings.max_ocr_text_length} character maximum. Verify a single document was submitted."
                    ),
                    severity="warning",
                )
            )

        alnum_count = len(_ALNUM_PATTERN.findall(stripped))
        alnum_ratio_percent = (alnum_count / len(stripped)) * 100
        if alnum_ratio_percent < settings.min_alnum_ratio_percent:
            issues.append(
                ValidationIssue(
                    code="OCR_TEXT_LOW_QUALITY",
                    message=(
                        f"OCR text is only {alnum_ratio_percent:.0f}% alphanumeric, "
                        f"below the {settings.min_alnum_ratio_percent}% threshold. Text may be garbled."
                    ),
                    severity="warning",
                )
            )

        is_valid = not any(issue.severity == "error" for issue in issues)
        return is_valid, issues
