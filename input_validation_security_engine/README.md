# Input Validation & Security Engine

Independent Phase 1 microservice for **Sahaay.AI**. It validates applicant
documents *before* they reach the AI Guidance Engine (Phase 2) or the
Trust & Governance Engine (Phase 4).

It is a sibling of `ai_guidance_engine/` — same layered architecture,
same naming conventions, own `app.py`, own `requirements.txt`, no imports
from any other module in the repo. Modules only ever talk to each other
through HTTP + these Pydantic contracts.

## Responsibilities

| Check | What it does |
|---|---|
| Document type validation | Confirms `type` is in the supported catalog (`aadhaar`, `income_certificate`, `age_proof`, etc.) |
| Metadata validation | MIME type allow-list, file size ceiling, page-count ceiling |
| OCR input validation | Rejects empty/near-empty text, flags too-long text, flags garbled/low-alphanumeric text |
| Required-document completeness | Given a `pension_type`, reports which required documents are still missing |
| Eligibility pre-check | Lightweight, **non-authoritative** age-gate check (e.g. Old Age Pension requires age ≥ 60) |
| Standardized response | Every call returns the same `ValidationResponse` shape regardless of what failed |

Eligibility pre-check is explicitly *not* a final decision — an under-age
applicant is routed to `manual_review`, not auto-rejected, because policy
exceptions exist. Final eligibility is Phase 4's responsibility.

## Run it

This module's `app.py` uses relative imports (`from .config import
settings`), so it must be run as part of the `input_validation_security_engine`
package from the **repo root** - not `python app.py` from inside the
folder, which fails with `ImportError: attempted relative import with no
known parent package`.

```bash
# from the repo root
pip install -r input_validation_security_engine/requirements.txt
uvicorn input_validation_security_engine.app:app --reload --port 8001
```

Copy `input_validation_security_engine/.env.example` to
`input_validation_security_engine/.env` to override any default.

Docs: `http://localhost:8001/docs`

## API

### `POST /api/v1/validate`

```bash
curl -X POST http://localhost:8001/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @input_validation_security_engine/sample_data/sample_valid_request.json
```

Request (`DocumentValidationRequest`):

```json
{
  "applicant_id": "123",
  "pension_type": "old_age",
  "applicant_age": 65,
  "documents": [
    { "type": "aadhaar", "text": "...", "metadata": { "file_name": "a.pdf", "mime_type": "application/pdf", "size_bytes": 12345, "page_count": 1 } }
  ]
}
```

`pension_type`, `applicant_age`, and per-document `metadata` are all
optional. Omitting `pension_type` skips the required-document and
eligibility checks (only per-document type/metadata/OCR checks run).

Response (`ValidationResponse`) — `status` is one of `valid`,
`manual_review`, or `invalid`:

```json
{
  "status": "valid",
  "engine": "Input Validation & Security Engine",
  "applicant_id": "123",
  "overall_valid": true,
  "documents": [ { "type": "aadhaar", "is_supported_type": true, "metadata_valid": true, "ocr_valid": true, "is_valid": true, "issues": [] } ],
  "missing_required_documents": [],
  "eligibility_pre_check": { "pension_type": "old_age", "is_age_eligible": true, "minimum_age_required": 60, "notes": [] },
  "issues_summary": []
}
```

### `GET /api/v1/document-types`

Reference endpoint. Returns the full supported document/pension type
catalog plus required-document rules, so the multilingual_guidance_ui and `system_orchestrator/`
don't need to hardcode these lists separately.

### `GET /health`

Liveness probe used by Phase 5 integration checks.

## Document / pension catalog

Document type codes are lowercase snake_case and line up 1:1 with the
`type` field already used by `ai_guidance_engine` (see
`ai_guidance_engine/sample_data/sample_request.json`).

Every pension type requires: `aadhaar`, `address_proof`, `bank_passbook`,
`passport_photo`, `income_certificate`, plus:

| Pension type | Extra required document |
|---|---|
| `old_age` | `age_proof` (and minimum age 60) |
| `widow` | `death_certificate` |
| `disability` | `disability_certificate` |
| `family_benefit` | `death_certificate` |

This is data, not branching logic — see
`input_validation_security_engine/models/document_types.py` — so a policy owner
can extend it without touching service code.

## Tests

```bash
cd input_validation_security_engine
pytest tests/ -v
```

Covers the API end-to-end (valid application, missing documents,
unsupported type, empty OCR text, under-age manual review, unknown
pension type, bad MIME type, empty document list → 422) and each service
in isolation.

## Integration notes (for Phase 5)

* A document that passes `is_supported_type` + `ocr_valid` here can be
  forwarded to `ai_guidance_engine` as-is — `DocumentValidationInput`
  (`type` + `text`) is a superset of `ai_guidance_engine`'s
  `DocumentInput`.
* `status: "invalid"` should block submission before extraction runs.
* `status: "manual_review"` should still allow extraction/review to
  proceed, but the caseworker UI (Phase 4) should surface
  `eligibility_pre_check.notes`.
* `GET /api/v1/document-types` is the single source of truth for the
  document/pension catalog — the frontend document-upload screen and
  `system_orchestrator/` should call it rather than duplicating the enum.
