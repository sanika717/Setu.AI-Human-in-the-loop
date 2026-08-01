# Official Service Registry

Config-driven catalog of every official government/banking service Sahaay.AI
can guide a user through. This is the piece of infrastructure that makes
Phase B generic: **no other module hardcodes a service name, document list,
eligibility rule, or official URL** - they all ask this registry over HTTP.

Runs independently on **port 8004**.

## Why this exists

Before Phase B, "pension" (and specifically NSAP Old Age/Widow/Disability/
Family Benefit pensions) was baked into enum classes and branching logic
across the Input Validation & Security Engine, the Trust & Governance
Engine, the AI Guidance Engine, and the System Orchestrator's portal
endpoints. That made every new service (Aadhaar update, SBI KYC, Passport,
PAN, LIC premium payment, ...) a code change in four different places.

The registry turns that into a data change in one file:
[`data/services.json`](data/services.json).

## What's in a service definition

```json
{
  "service_id": "nsap_old_age_pension",
  "service_name": "National Social Assistance Programme - Old Age Pension",
  "category": "pension",
  "official_url": "https://nsap.nic.in",
  "allowed_domains": ["nsap.nic.in"],
  "required_documents": ["aadhaar", "address_proof", "..."],
  "eligibility_rules": [
    {"field": "applicant_age", "operator": "gte", "value": 60, "message": "..."}
  ],
  "workflow_steps": [
    {"step_id": "detect_intent", "title": "...", "action_type": "intent_confirmation", "description": "..."}
  ],
  "supported_languages": ["en", "hi"]
}
```

`eligibility_rules` are evaluated generically by
[`services/eligibility_engine.py`](services/eligibility_engine.py) against
whatever `applicant_context` dict a caller supplies - the engine only knows
about comparison operators (`gte`, `lte`, `gt`, `lt`, `eq`, `ne`, `in`,
`exists`), never about "pension" or "age" specifically.

## Adding a new service

1. Add an entry to `data/services.json` (or whatever file `SERVICES_CONFIG_PATH`
   points at).
2. `POST /api/v1/admin/reload` (or just restart the process).
3. Done - every other Sahaay.AI service that queries the registry
   (`GET /api/v1/services`, `/missing-documents`, `/eligibility`,
   `/redirect`, `/workflow`) immediately sees it. No code changes anywhere.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/services` | List every registered service (summary) |
| GET | `/api/v1/services/{service_id}` | Full service definition |
| POST | `/api/v1/services/{service_id}/missing-documents` | Diff submitted vs. required documents |
| POST | `/api/v1/services/{service_id}/eligibility` | Evaluate `eligibility_rules` against an `applicant_context` |
| GET | `/api/v1/services/{service_id}/redirect` | The ONLY official URL + domain whitelist Sahaay.AI will ever redirect a user to for this service |
| GET | `/api/v1/services/{service_id}/workflow` | Ordered workflow steps for this service |
| POST | `/api/v1/admin/reload` | Re-read services.json from disk |
| GET | `/health` | Liveness/readiness probe |

## Run it

```bash
cd official_service_registry
cp .env.example .env
pip install -r requirements.txt
uvicorn app:app --port 8004
```

Or from the repo root: `python -m official_service_registry.app`.

## Consumers

- **Input Validation & Security Engine** (`:8001`) calls
  `/missing-documents` and `/eligibility` instead of hardcoding pension
  document/age rules.
- **System Orchestrator** (`:8000`) calls `/services` and `/redirect` to
  drive `/api/v1/portals` and `/api/v1/portals/confirm` - it never hardcodes
  a portal list.
- **AI Guidance Engine** (`:8002`) can be pointed at a `service_id` to
  extract the right fields for that service (Phase C wires this up fully
  for voice/text intent detection; Phase B already accepts an explicit
  `service_type` / `target_fields`).
- **Multilingual Guidance UI** fetches `/services` directly to populate the
  service picker instead of a hardcoded pension dropdown.
