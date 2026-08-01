import re

from ..models.field_models import ExtractedField

# Hedging language the model itself uses when it is not confident (ambiguous
# OCR, guessed values, illegible text). Presence of this signal is a much
# stronger indicator of unreliable extraction than "was a value present".
_HEDGE_PATTERN = re.compile(
    r"\b("
    r"unclear|uncertain|illegible|not clear|hard to read|possibly|might be|"
    r"guess(?:ed)?|ambiguous|partial(?:ly)?|blurred|blurry|cannot confirm|"
    r"not confident|low quality|garbled"
    r")\b",
    re.IGNORECASE,
)


class ConfidenceService:
    """Assigns confidence scores and levels to extracted values.

    Scoring combines three signals rather than a single presence check:
    - Whether a value was extracted at all (no value -> 0 confidence).
    - Whether the model's own stated reasoning contains hedging language
      (e.g. "illegible", "possibly", "blurred") - a hedge lowers confidence
      even when a value is present, because the model is telling us it
      isn't sure.
    - Whether a source document was attributed and reasoning was given at
      all, since an unattributed, unexplained value is harder for a human
      reviewer to verify and should not be treated as high-confidence.
    """

    HIGH_CONFIDENCE = 0.95
    MEDIUM_CONFIDENCE = 0.7
    LOW_MEDIUM_CONFIDENCE = 0.5
    HEDGED_CONFIDENCE = 0.35
    HEDGED_WITH_SOURCE_CONFIDENCE = 0.45
    NO_VALUE_CONFIDENCE = 0.0

    def score(self, value: str | None, reason: str, source_document: str) -> tuple[float, str]:
        if value is None or not value.strip():
            return self.NO_VALUE_CONFIDENCE, "Low"

        reason_text = reason or ""
        is_hedged = bool(_HEDGE_PATTERN.search(reason_text))
        has_source = bool(source_document and source_document.strip() and source_document != "Unknown")
        has_reason = bool(reason_text.strip())

        if is_hedged:
            confidence = self.HEDGED_WITH_SOURCE_CONFIDENCE if has_source else self.HEDGED_CONFIDENCE
            return confidence, "Low"

        if has_source and has_reason:
            return self.HIGH_CONFIDENCE, "High"

        if has_source or has_reason:
            return self.MEDIUM_CONFIDENCE, "Medium"

        return self.LOW_MEDIUM_CONFIDENCE, "Medium"

    def build_field(self, field_name: str, value: str | None, source_document: str, reason: str) -> ExtractedField:
        confidence, confidence_level = self.score(value, reason, source_document)
        return ExtractedField(
            field=field_name,
            value=value,
            confidence=confidence,
            confidence_level=confidence_level,
            source_document=source_document,
            reason=reason,
        )
