# Trust & Governance Engine

Independent Phase 4 microservice for **Sahaay.AI**. It is where a human
caseworker reviews the fields the AI Guidance Engine (Phase 2) pulled out
of an applicant's documents, decides what happens to each one, and gates
final submission behind OTP verification and a tamper-evident audit trail.

It is a sibling of `ai_guidance_engine/` and `input_validation_security_engine/`
— same layered architecture (`api/`, `models/`, `services/`, `utils/`), own
`app.py`, own `requirements.txt`, its own database, and no imports from any
other module in the repo. Every module talks to this one only over HTTP.

## Responsibilities

| Capability | What it does |
|---|---|
| Application intake | Accepts the extracted-fields list produced by Phase 2 and creates a governed application |
| Approve / reject / edit | A caseworker can approve a field as-is, reject it (with a reason), or edit its value (which also approves the corrected value) |
| Status engine | Application status (`draft` → `under_review` → `ready_for_submission` / `validation_failed` → `submitted`) is recomputed automatically from field decisions |
| OTP verification | A one-time code gates final submission; generation, hashing (PBKDF2 + pepper), expiry, and attempt-limiting are fully implemented. Delivery is pluggable — see `OTPDeliveryProvider` — since there's no SMS/e-mail provider in this codebase yet, so it defaults to a console/dev-mode provider that echoes the code back in the API response |
| Trusted Delegate (Phase F) | An applicant can name a Trusted Person (family member, caregiver, NGO volunteer) who must additionally approve the application before submission — on top of, never instead of, OTP. Registering one requires recording who gave consent (`consent_given_by`); only one delegate is active at a time, and superseding or revoking one keeps its history rather than deleting it |
| Submission validation | `GET .../submission/validate` reports every reason an application can't yet be submitted, without mutating anything |
| Final submission | `POST .../submit` snapshots only the approved fields, computes a submission hash, and locks the application — no further field decisions are accepted afterward |
| Immutable audit log | Every decision, OTP event, and submission is recorded to a hash-chained, append-only log; `GET .../audit-log/verify` recomputes the chain and reports whether it's intact |
| Reports | `GET .../report?format=csv\|json\|pdf` builds a decision-and-audit report in any of the three formats |

## Run it

This module's `app.py` uses relative imports (`from .config import
settings`), so it must be run as part of the `trust_governance_engine` package
from the **repo root** - not `python app.py` from inside the folder, which
fails with `ImportError: attempted relative import with no known parent
package`.

```bash
# from the repo root
pip install -r trust_governance_engine/requirements.txt
uvicorn trust_governance_engine.app:app --reload --port 8003
```

Copy `trust_governance_engine/.env.example` to `trust_governance_engine/.env` to
override any default (OTP pepper, database URL, etc.).

Docs: `http://localhost:8003/docs`

By default this engine keeps its own SQLite database (`governance.db`,
created inside this package's own directory regardless of where you launch
the process from), independent of `system_orchestrator/app`'s database. Point
`DATABASE_URL` at Postgres (with an async driver, e.g.
`postgresql+asyncpg://...`) for production.

## API

### `POST /api/v1/applications`

Create an application from an intake payload (see
`sample_data/sample_application_intake.json`):

```bash
curl -X POST http://localhost:8003/api/v1/applications \
  -H "Content-Type: application/json" \
  -d @trust_governance_engine/sample_data/sample_application_intake.json
```

### Field decisions

```
POST /api/v1/applications/{application_id}/fields/{field_name}/approve
POST /api/v1/applications/{application_id}/fields/{field_name}/reject
POST /api/v1/applications/{application_id}/fields/{field_name}/edit
```

### Status & submission

```
GET  /api/v1/applications/{application_id}
GET  /api/v1/applications/{application_id}/status
GET  /api/v1/applications/{application_id}/submission/validate
POST /api/v1/applications/{application_id}/otp/request
POST /api/v1/applications/{application_id}/otp/verify
POST /api/v1/applications/{application_id}/submit
```

### Trusted Delegate (Phase F)

```
POST /api/v1/applications/{application_id}/delegate           # register (supersedes any previous active delegate)
GET  /api/v1/applications/{application_id}/delegate            # the currently active delegate, if any
POST /api/v1/applications/{application_id}/delegate/approve
POST /api/v1/applications/{application_id}/delegate/revoke
```

If a delegate is registered with `approval_required: true` (the default),
`submission/validate` and `submit` will both block until that delegate
approves — the same way they already block on an unverified OTP.

### Audit log & reports

```
GET /api/v1/applications/{application_id}/audit-log
GET /api/v1/applications/{application_id}/audit-log/verify
GET /api/v1/applications/{application_id}/report?format=csv|json|pdf
```

## Testing

```bash
cd trust_governance_engine
pytest
```

Tests spin up a scratch SQLite database (`test_governance.db`) via
`conftest.py` and exercise the full review → OTP → submission → audit →
report flow end-to-end, plus the Trusted Delegate register → approve/revoke
→ submission-gating flow (`tests/test_governance_api.py`).

## Design notes

- **Status is derived, never set directly.** `DecisionService._recompute_status`
  is the only place application status changes; it's driven entirely by the
  set of field decisions, so the status can never drift out of sync with
  the fields.
- **OTP re-invalidation.** If a field decision changes after OTP has been
  verified (e.g. a caseworker re-opens a previously-approved field), the
  verification is cleared automatically — a verified OTP always corresponds
  to the data that was actually verified.
- **Submitted applications are immutable.** `ApplicationLockedError` is
  raised on any attempted mutation once `status == submitted`.
- **Audit log is append-only and hash-chained.** Every entry's hash covers
  its own content plus the previous entry's hash (SHA-256), so tampering
  with or deleting any historical row breaks the chain from that point
  forward — detectable via `AuditService.verify_chain`.
