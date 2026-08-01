from typing import Any

from ..models.field_models import ExtractedField
from ..utils.exceptions import InvalidResponseError


class ParserService:
    """Parses provider output into standardized extraction fields."""

    def parse(self, payload: dict[str, Any], source_document: str, confidence_service: Any) -> list[ExtractedField]:
        fields_payload = payload.get("fields", [])
        if not isinstance(fields_payload, list):
            raise InvalidResponseError("Provider response did not contain a valid fields list")

        parsed_fields: list[ExtractedField] = []
        for item in fields_payload:
            if not isinstance(item, dict):
                continue
            field_name = str(item.get("field", "Unknown Field"))
            value = item.get("value")
            if value is not None:
                value = str(value)
            source = str(item.get("source_document") or source_document)
            reason = str(item.get("reason") or "Extracted from provided document text")
            parsed_fields.append(
                confidence_service.build_field(field_name, value, source, reason)
            )
        return parsed_fields
