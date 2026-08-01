import json
from typing import Any


DEFAULT_SCHEMA_FIELDS: list[dict[str, str]] = [
    {"field": "Applicant Name", "type": "string"},
    {"field": "Date of Birth", "type": "string"},
    {"field": "Service Type", "type": "string"},
    {"field": "Address", "type": "string"},
]


class PromptBuilder:
    """Builds dynamic prompts for extraction tasks.

    As of Phase B this is service-agnostic: the extraction schema no longer
    hardcodes "Pension Type" - it uses the generic "Service Type" field by
    default, and callers guiding a specific Official Service Registry
    service (e.g. `nsap_old_age_pension`, `sbi_kyc_update`) can pass
    `service_id` and/or `target_fields` to tailor the extraction schema to
    that service without any code change here.
    """

    def build_prompt(
        self,
        documents: list[dict[str, Any]],
        applicant_id: str,
        service_id: str | None = None,
        target_fields: list[str] | None = None,
    ) -> str:
        document_summaries = []
        for document in documents:
            document_summaries.append(
                {
                    "type": document.get("type", "unknown"),
                    "text": document.get("text", ""),
                }
            )

        if target_fields:
            schema = {"fields": [{"field": field_name, "type": "string"} for field_name in target_fields]}
        else:
            schema = {"fields": list(DEFAULT_SCHEMA_FIELDS)}

        service_line = f"\nThe applicant is applying for the official service: {service_id}.\n" if service_id else ""

        return f"""
You are an expert document extraction engine.
Extract the requested fields from the provided documents for applicant_id={applicant_id}.{service_line}
Return ONLY valid JSON matching this schema:
{json.dumps(schema, indent=2)}

Documents:
{json.dumps(document_summaries, indent=2)}

Rules:
- Extract values only when confidently supported by the text.
- If uncertain, set the value to null.
- Return a JSON object with a "fields" array.
- Each item must include: field, value, confidence, confidence_level, source_document, reason.
"""
