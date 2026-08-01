# AI Banking Guide Frontend (Phase 3)

Plain HTML/CSS/JS frontend for Sahaay.AI. No build step, no framework — open
`index.html` through a static server and it talks to five independent
backend services over plain `fetch()` calls.

## What's on the page

1. **Document Upload & Hash** — picks a file, computes its SHA-256 client-side,
   and stores it via `system_orchestrator/app` (`POST /api/v1/documents`). For text-based
   files, the extracted text is also kept in memory so it can be reused below.
2. **Document Validation** — sends one or more documents (type + OCR text +
   optional metadata) to the `input_validation_security_engine` (Phase 1) via
   `POST /api/v1/validate`, and renders per-document issues, missing required
   documents, and the eligibility pre-check. The supported document type
   catalog is loaded from `GET /api/v1/document-types` (validation engine) and
   used to populate the OCR-text autocomplete list. The "Service" dropdown is
   loaded from the `official_service_registry` via `GET /api/v1/services` and
   sends the chosen `service_id` with the validate request — required-document
   and eligibility pre-checks work for any registered service (pension,
   Aadhaar, SBI KYC, Passport, PAN, LIC, etc.), not just pensions.
3. **Ask Sahaay.AI** — a chat box that sends free-form text (e.g. "I want to
   apply for old age pension") to `system_orchestrator/app`
   (`POST /api/v1/conversation/message`), which proxies to `intent_service`
   (Phase C1-C4) and relays the reply back verbatim. This is a thin,
   additive second entry point into the guidance flow, not a replacement for
   section 4:
   - Renders `intent_service`'s reply as a chat bubble, and (while
     disambiguating between a few close-scoring services) shows each
     candidate as a clickable chip — clicking one sends its 1-based index as
     the next message, which is exactly what typing e.g. `"1"` or the
     service's name by hand would also do.
   - Once the conversation reaches `state: "completed"` with a
     `resolved_service`, shows a **"Continue to official site"** button.
     That button calls the *same* `confirmPortalRedirect()` helper section
     4's portal cards use (refactored out into a shared function, not
     duplicated) — so the confirmation prompt and the Phase D Security
     Shield check (`POST /api/v1/portals/confirm` → `risk_engine`) apply
     identically whether the citizen got there by chatting or by clicking a
     card.
   - **"Start Over"** clears local chat state and best-effort calls
     `DELETE /api/v1/conversation/{id}` so the citizen can begin a fresh
     conversation without waiting for the session to idle out.
   - `conversation_id` is tracked in memory only (a page reload starts a new
     conversation) — there is no persistence across browser sessions today.
4. **Guided Banking Portal** — lists government banking portals from
   `system_orchestrator/app` (`GET /api/v1/portals`) and asks for explicit confirmation
   before every redirect (`POST /api/v1/portals/confirm`). Completely
   unmodified by the Ask Sahaay.AI addition above — every existing test and
   behavior for this section still applies unchanged.
5. **AI Field Extraction** — sends documents to the `ai_guidance_engine`
   (Phase 2) via `POST /api/v1/extract` and renders each extracted field with
   its confidence level and source document.
6. **Human Review & Governance** — hands the last extraction result straight
   to the `trust_governance_engine` (Phase 4) via `POST /api/v1/applications`, or
   loads an existing application by ID. From there a caseworker can:
   - approve / reject / edit each field individually,
   - request and verify an OTP once every field has a decision,
   - check submission readiness (`GET .../submission/validate`) and submit
     (`POST .../submit`), which locks the application,
   - load and verify the immutable, hash-chained audit log
     (`GET .../audit-log`, `GET .../audit-log/verify`), and
   - download a CSV/JSON/PDF decision report (`GET .../report?format=...`).
   - register/load/approve/revoke a **Trusted Delegate** for the loaded
     application (`POST`/`GET .../delegate`, `POST .../delegate/approve`,
     `POST .../delegate/revoke` on `trust_governance_engine`) — the Human-in-
     the-Loop trusted-person feature from Phase F. When "approval required"
     is checked, submission readiness (and the Submit button's underlying
     call) stays blocked until the delegate approves; the panel shows the
     delegate's status (awaiting approval / approved / revoked) and is
     auto-loaded whenever an application is loaded.

   The "Caseworker ID" field at the top of the section is sent as the
   `actor` on every decision, OTP action, and submission, so the audit log
   records who did what.

Section 4 (**Guided Banking Portal**) also renders the Phase D Security
Shield's pause state: if `POST /api/v1/portals/confirm` comes back `409`
(risk_engine flagged the redirect - not on the official domain whitelist,
missing HTTPS, etc.), the portal feedback area shows a distinct red
"redirect paused by the Security Shield" panel listing every finding,
instead of a generic error string. Sahaay.AI never auto-retries or
overrides that pause. Section 3's "Continue to official site" button
renders the same pause panel (in its own feedback area) for the same
reason, since it shares the same underlying confirm call.

Each doc-row in sections 2 and 5 has a **"Use last upload"** button that pulls
the most recently uploaded file's text (and, in Validation, its file
name/MIME type/size) straight into that row, so you don't have to copy/paste
OCR text between sections by hand.

> **Known limitation:** "Use last upload" only works for plain text files —
> it reads the file client-side with `file.text()`. It is **not** image OCR.
> Scanned documents (PDF/JPEG/PNG) still need their OCR'd text pasted into the
> "OCR Text" field manually, because no OCR provider is wired into the
> backend yet. Only the *validity* of already-extracted OCR text is checked
> today (length, alphanumeric ratio, etc.) — see
> `input_validation_security_engine/services/ocr_input_service.py`.

## Services & ports

This frontend directly calls five separate FastAPI processes, each with its
own `ALLOWED_ORIGINS`-driven CORS policy. `system_orchestrator` in turn
calls two more (`risk_engine`, `intent_service`) server-side on the
frontend's behalf, so **seven** processes total need to be running for
every feature on this page to work end-to-end:

| Service                      | Default URL                  | Start command (from repo root)                                                    |
|-------------------------------|-------------------------------|-------------------------------------------------------------------------------------|
| `system_orchestrator/app`                 | `http://127.0.0.1:8000`       | `cd system_orchestrator && uvicorn app.main:app --reload --port 8000`                           |
| `input_validation_security_engine`  | `http://127.0.0.1:8001`       | `uvicorn input_validation_security_engine.app:app --reload --port 8001`                   |
| `ai_guidance_engine`        | `http://127.0.0.1:8002`       | `uvicorn ai_guidance_engine.app:app --reload --port 8002`                         |
| `trust_governance_engine`           | `http://127.0.0.1:8003`       | `uvicorn trust_governance_engine.app:app --reload --port 8003`                            |
| `official_service_registry`        | `http://127.0.0.1:8004`       | `uvicorn official_service_registry.app:app --reload --port 8004`                  |
| `risk_engine` *(called by `system_orchestrator`, not directly by this UI)* | `http://127.0.0.1:8005` | `uvicorn risk_engine.app:app --reload --port 8005` |
| `intent_service` *(called by `system_orchestrator`, not directly by this UI)* | `http://127.0.0.1:8006` | `uvicorn intent_service.app:app --reload --port 8006` |

`system_orchestrator` is run from inside its own folder (its entry point is the nested
package `app.main`). The other six are run **from the repo root** as
dotted module paths — their `app.py` sits at the top of the package and
uses relative imports (`from .config import settings`), so `cd <folder> &&
uvicorn app:app` breaks with `ImportError: attempted relative import with
no known parent package`.

Install each service's own `requirements.txt` first (e.g.
`pip install -r system_orchestrator/requirements.txt`, and similarly for the other six).
`input_validation_security_engine` and `system_orchestrator` both call
`official_service_registry` over HTTP (`registry_base_url`, default
`http://127.0.0.1:8004`) and degrade gracefully (a warning, not a crash) if
it isn't running — but the Service dropdown and live required-document/
eligibility checks in this UI need it up to show anything beyond the static
fallback portal list. `system_orchestrator` also calls `risk_engine`
(`POST /api/v1/portals/confirm` → `POST /api/v1/risk/redirect-check`) and,
as of the conversational guidance integration, `intent_service`
(`/api/v1/conversation/*`, proxied verbatim) — both fail closed/degrade
gracefully rather than crashing `system_orchestrator` if unreachable (a
502 for the conversation routes; a skipped/warned check for the redirect
risk check), but section 3 ("Ask Sahaay.AI") needs `intent_service` running
to do anything, and section 4's redirects need `risk_engine` running for
the Security Shield check to actually verify anything rather than just
warn.

Then serve the frontend itself from this folder:

```bash
cd multilingual_guidance_ui
python -m http.server 8080
```

Open `http://127.0.0.1:8080` in your browser.

### Pointing at different hosts/ports

The five base URLs are read from `window.SAHAAY_CONFIG` if it's set before
`app.js` loads, falling back to the defaults above. To point at a
non-default host without editing `app.js`, add an inline script above the
`app.js` `<script>` tag in `index.html`:

```html
<script>
  window.SAHAAY_CONFIG = {
    backendBase: "https://api.example.com/api/v1",
    validationBase: "https://validate.example.com/api/v1",
    extractionBase: "https://extract.example.com/api/v1",
    governanceBase: "https://governance.example.com/api/v1",
    registryBase: "https://registry.example.com/api/v1",
  };
</script>
```

## Notes

- Every redirect to a banking portal asks for user confirmation first.
- Uploaded documents are hashed client-side (SHA-256) and sent to
  `system_orchestrator/app` for secure, encrypted persistence.
- All four services need CORS enabled for the frontend's origin. Each
  ships with `ALLOWED_ORIGINS` defaulting to `*` for local development —
  set it explicitly (comma-separated origins) before deploying anywhere
  public.
- Section 5 works from either an extraction just run in section 4, or any
  existing application ID — you don't have to re-run extraction to resume
  reviewing an application from a previous session.
- OTP delivery has no real SMS/e-mail provider wired in yet (see the
  `trust_governance_engine` README), so `governance.otp_dev_mode_expose_code`
  defaults to `true` and the code is shown directly in the "Request OTP"
  result so the flow can be exercised end-to-end.
- Section 3's `conversation_id` is held in a plain JS variable, not
  `localStorage`/`sessionStorage` or a cookie — reloading the page starts a
  brand-new conversation. `intent_service` itself does keep the
  conversation server-side (so `GET /api/v1/conversation/{id}` would still
  work if you had the id), but this UI doesn't persist the id anywhere to
  look it back up after a reload.

## Not yet built (out of scope for Phase 3/4)

- **`/evaluate` and `/rag`** — both exist on `system_orchestrator/app` but aren't part of
  the Phase 3 brief (document validation + AI extraction), so there's no UI
  for them here.
- **Auth / applicant sessions** — `applicant_id` and "Caseworker ID" are
  plain text fields typed into each form; there's no login or token
  handling. Fine for a local demo, not for production.
- **Bulk/list views** — the governance panel reviews one application at a
  time (from an extraction or a pasted ID); there's no UI yet for browsing
  `GET /api/v1/applications` across every applicant.
