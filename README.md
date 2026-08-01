# Sahaay.AI

A multilingual AI Digital Trust & Guidance Platform that guides citizens
through official government and banking websites. It never replaces an
official website, never stores passwords/OTPs/PINs, and keeps a human in
control at every sensitive step (Human-in-the-Loop).

The project is built as a set of small, independent FastAPI microservices —
one per phase — plus a plain HTML/CSS/JS UI that talks to all of them. Every
service keeps its own dependencies, its own database, and its own `app.py`;
nothing imports across service boundaries, only HTTP.

## Phase B: module rename (current)

As of Phase B the four backend microservices and the UI were renamed to the
vocabulary used across the rest of this project, per the mapping below. The
rename is a **folder + display-name rename only** — no business logic,
endpoints, request/response schemas, or ports changed. Every previous name
still works: each old folder is now a thin backward-compatible alias package
that re-exports the renamed package (see "Backward compatibility" below), so
existing scripts, deployment configs, or imports that still use the old
names keep working unchanged.

| Old name (Phase A) | New name (Phase B) | Folder |
|---|---|---|
| Backend | System Orchestrator | `system_orchestrator/` |
| Document Validation Engine | Input Validation & Security Engine | `input_validation_security_engine/` |
| AI Extraction Engine | AI Guidance Engine | `ai_guidance_engine/` |
| Governance Engine | Trust & Governance Engine | `trust_governance_engine/` |
| Frontend | Multilingual Guidance UI | `multilingual_guidance_ui/` |

## Phases & services

| Phase | Service | Folder | Default port | Status |
|---|---|---|---|---|
| 0 | Common contracts & shared standards | (Pydantic contracts inside each service) | — | In place |
| 1 | Input Validation & Security Engine | `input_validation_security_engine/` | `8001` | Complete (Phase A); renamed (Phase B) |
| 2 | AI Guidance Engine | `ai_guidance_engine/` | `8002` | Complete (Phase A); renamed (Phase B) |
| — | System Orchestrator (uploads, portal redirects, eval/RAG) | `system_orchestrator/` | `8000` | Complete (Phase A); renamed (Phase B) |
| 3 | Multilingual Guidance UI | `multilingual_guidance_ui/` | `8080` (static) | Complete (Phase A); renamed (Phase B) |
| — | Official Service Registry (service catalog, domain whitelist source) | `official_service_registry/` | `8004` | Complete (Phase B) |
| 4 | Trust & Governance Engine (incl. Trusted Delegate) | `trust_governance_engine/` | `8003` | Complete (Phase A/B); Trusted Delegate added |
| D | Risk Engine (Security Shield: HTTPS + domain whitelist + sensitive-field detection) | `risk_engine/` | `8005` | Minimal, real implementation — see "Not yet done" |
| C1–C4 | Intent Service (text-only + multilingual intent classification, service directory lookup, multi-turn conversation) | `intent_service/` | `8006` | Complete, and now integrated end-to-end via `system_orchestrator` + the UI — see "Conversational guidance integration" below |
| 5 | Integration | (this README + cross-service testing) | — | Ongoing |

## Phase C roadmap (Intent & Service Discovery)

Phase C is being delivered incrementally, one small, independently testable
milestone at a time, rather than as one large batch:

| Sub-phase | Scope | Status |
|---|---|---|
| **C1** | Natural-language intent classification, text-only input, modular classifier design, no voice yet | **Complete** — `intent_service/`, `POST /api/v1/intent/classify` |
| **C2** | Official Service Directory lookup: map a classified intent to an `official_service_registry` `service_id`, with ranking/confidence over the catalog | **Complete** — `intent_service/`, `POST /api/v1/intent/resolve` |
| **C3** | Multilingual support: offline script-based language detection, per-language keyword taxonomies (English, Hindi, Marathi, Bengali, Tamil, Telugu), language-aware service ranking | **Complete** — `intent_service/providers/language_detector.py`, `data/intents_<code>.json`, `language`/`language_source`/`language_supported` fields on both endpoints |
| **C4** | Conversation/context management: follow-up questions, missing-information prompts, disambiguation, autofill, eligibility resolution | **Complete** — `intent_service/services/conversation_manager.py`, `POST /api/v1/conversation/message` |
| C5 (optional) | Voice/STT pipeline, audio processing | Not started |

**Phase C consolidation.** C1-C4 were built incrementally, one zip per
sub-phase. A consolidation pass then folded them into one cohesive module:
`ConversationMessageRequest` (C4) now inherits its shared fields from
`IntentClassifyRequest` (C1) instead of re-declaring them, `api/dependencies.py`
builds a single `RegistryClient` shared between C2's `ServiceLookupService`
and C4's `ConversationManager` instead of two, and a new
`intent_service/tests/test_phase_c_integration.py` end-to-end suite proves
C1→C2→C3→C4 agree with each other through the real HTTP API (not just that
each responds independently) — see `intent_service/README.md`'s "Phase C
consolidation" section for the full writeup. No endpoint, request/response
shape, or existing test was changed; this was a dedup-only pass. Phase C
remains intentionally standalone — it is not yet wired into Phases A/B
(`system_orchestrator`, `multilingual_guidance_ui`, etc.); that integration
is future work, not part of this pass.

`intent_service/` was deliberately standalone through the Phase C consolidation
pass. `POST /intent/classify` (C1) has zero inter-service dependencies.
`POST /intent/resolve` (C2) additionally calls `official_service_registry`
for the live service catalog to rank against, but degrades gracefully (200
with `registry_available: false`) if that service is down — it never
hard-fails just because a dependency isn't running, per the Phase A "every
microservice runs independently" rule. C3
(`providers/language_detector.py`, `providers/factory.create_classifier_for_language`)
plugs into the same `BaseIntentClassifier` seam C1 left open, so neither
endpoint's existing request/response contract changed — `language` is an
optional request field, and `language_name`/`language_source`/
`language_detection_confidence`/`language_supported` were only added to the
response, never replacing an existing field. `intent_service` itself is
still untouched by the integration described below — `system_orchestrator`
only calls its existing `POST /api/v1/conversation/*` endpoints over HTTP,
exactly as any other client of `intent_service` would.

Each service has its own `README.md` with full endpoint documentation,
design notes, and a "run it" section — start there for details on any one
piece. This file is the map of how they fit together.

## Conversational guidance integration (system_orchestrator ↔ intent_service)

`intent_service` (Phase C1-C4) is now wired into the rest of the platform.
Some of the source material for this pass calls it "Phase D"; in this
repo's own phase lettering (inherited from the master prompt) "Phase D" was
already assigned to `risk_engine`/Security Shield above, so this section
uses "the conversational guidance integration" to avoid clashing with that
established label — the two are unrelated pieces of work.

**Design, per the approved integration plan:**

- **`system_orchestrator` is the single integration point** between the
  frontend and `intent_service`. `multilingual_guidance_ui` never calls
  `intent_service` directly; it only calls `system_orchestrator`'s
  `/api/v1/conversation/*`, which proxies to `intent_service` over HTTP.
  `intent_service` itself was not modified at all for this integration —
  see `system_orchestrator/app/services/intent_client.py`.
- **No new linking model.** A completed conversation's
  `resolved_service.service_id` is the exact same identifier the pre-existing
  `GET /api/v1/portals` / `POST /api/v1/portals/confirm` flow already uses
  as `portal_id`. The UI hands that id straight to the existing confirm
  step; no new schema was introduced to bridge the two.
- **Additive only — the portal-card flow is untouched.** `GET /api/v1/portals`
  and `POST /api/v1/portals/confirm` behave exactly as before Phase D;
  `multilingual_guidance_ui/app.js`'s `confirmPortalRedirect()` helper
  (refactored out of the existing portal-card click handler, not
  rewritten) is now called from *both* the portal cards (section 4) and the
  new conversational section (section 3), so Security Shield handling and
  the confirmation prompt behave identically from either entry point.
- **New routes (thin proxies only, `system_orchestrator/app/api/routes.py`):**
  - `POST /api/v1/conversation/message` — forwards one turn to
    `intent_service`'s `POST /api/v1/conversation/message`.
  - `GET /api/v1/conversation/{conversation_id}` — read-only state fetch,
    for resuming after a page reload.
  - `DELETE /api/v1/conversation/{conversation_id}` — explicit reset.
  - All three degrade to `502 Bad Gateway` (never a crash, never a silent
    fallback to a fake response) if `intent_service` is unreachable, and
    leave every other route on `system_orchestrator` completely unaffected
    — see `system_orchestrator/app/tests/test_conversation_proxy.py`.
- **UI (`multilingual_guidance_ui`): new "3. Ask Sahaay.AI" section**,
  a chat box that sends free-form text to
  `POST /api/v1/conversation/message`, renders `intent_service`'s reply,
  shows disambiguation candidates as clickable chips (sending the picked
  option's 1-based index — the same input `intent_service`'s
  disambiguation handler already accepts from typed text), and once the
  conversation reaches `state: "completed"` with a `resolved_service`,
  shows a "Continue to official site" button that calls the *existing*
  `confirmPortalRedirect()` helper with that service's id — reusing the
  Security-Shield-checked redirect path, not a new one. The old section 3
  ("Guided Banking Portal") is renumbered to section 4; no markup or logic
  inside it changed.

**Tests:** `system_orchestrator/app/tests/test_conversation_proxy.py`
covers the proxy routes with an in-memory fake `IntentClient` (dependency
override, same technique the rest of this codebase's test suites use for
external HTTP dependencies) — a message being proxied and relayed, GET/DELETE
including 404 passthrough, `intent_service` unavailability producing a 502
without affecting other routes, and the end-to-end proof that a resolved
conversation's `service_id` works unmodified with the pre-existing
`POST /api/v1/portals/confirm`. The existing portal-only test in
`test_api.py` is unchanged and still passes, confirming backward
compatibility.

## Backward compatibility

Each renamed Python package left a one-file alias behind at its old import
path (e.g. `document_validation_engine/__init__.py`) that transparently
redirects to the new package via `sys.modules`. This means:

- `import document_validation_engine` (and any of its submodules) still
  resolves to `input_validation_security_engine`, unchanged.
- `uvicorn document_validation_engine.app:app --port 8001` still starts the
  same service as `uvicorn input_validation_security_engine.app:app --port
  8001`.
- The same holds for `ai_extraction_engine` → `ai_guidance_engine` and
  `governance_engine` → `trust_governance_engine`.

New code, scripts, and docs should use the new names going forward; the old
names exist purely so nothing that already depends on them breaks during the
transition. They may be removed in a later phase once nothing references
them.

## Running everything locally

Install each service's own dependencies first (from the repo root):

```bash
pip install -r system_orchestrator/requirements.txt
pip install -r input_validation_security_engine/requirements.txt
pip install -r ai_guidance_engine/requirements.txt
pip install -r trust_governance_engine/requirements.txt
pip install -r official_service_registry/requirements.txt
pip install -r risk_engine/requirements.txt
pip install -r intent_service/requirements.txt
```

Copy each service's `.env.example` to `.env` (see each file for what it
configures) — `system_orchestrator/app/.env.example`,
`input_validation_security_engine/.env.example`,
`ai_guidance_engine/.env.example`, `trust_governance_engine/.env.example`,
`official_service_registry/.env.example`, `risk_engine/.env.example`.

Then start each service. **`system_orchestrator` is run from inside its own
folder** (its entry point is the nested package `app.main`); **the others
are run from the repo root** as dotted module paths, because their
`app.py` sits at the top of the package and uses relative imports internally
(`from .config import settings`) — running them via `cd <folder> &&
uvicorn app:app` instead breaks with `ImportError: attempted relative
import with no known parent package`, since that loads `app.py` as a bare
top-level module instead of as part of the package:

```bash
# System Orchestrator (documents, portals, evaluation, RAG)
# - run from inside system_orchestrator/
cd system_orchestrator && uvicorn app.main:app --reload --port 8000 && cd ..

# Phase 1: Input Validation & Security Engine - run from the repo root
uvicorn input_validation_security_engine.app:app --reload --port 8001

# Phase 2: AI Guidance Engine - run from the repo root
uvicorn ai_guidance_engine.app:app --reload --port 8002

# Phase 4: Trust & Governance Engine - run from the repo root
uvicorn trust_governance_engine.app:app --reload --port 8003

# Official Service Registry (service catalog + domain whitelist source)
# - run from the repo root
uvicorn official_service_registry.app:app --reload --port 8004

# Phase D: Risk Engine (Security Shield) - run from the repo root
uvicorn risk_engine.app:app --reload --port 8005

# Phase C1: Intent Service (text-only intent classification) - run from the repo root
uvicorn intent_service.app:app --reload --port 8006

# Phase 3: Multilingual Guidance UI (static, no build step)
cd multilingual_guidance_ui && python -m http.server 8080 && cd ..
```

Open `http://127.0.0.1:8080` once all backends are running. The UI's
base URLs for each service default to the ports above and can be overridden
via `window.SAHAAY_CONFIG` — see `multilingual_guidance_ui/README.md`.
`official_service_registry` and `risk_engine` are optional for a basic
local run — `system_orchestrator` falls back to a static portal list if the
registry is unreachable, and fails open (logs a warning, skips the check)
if the risk engine is unreachable — but both should be running for the
Security Shield checks to actually verify anything.

## How a request flows through the phases

1. **Find the right service** (optional, conversational) — instead of (or
   before) browsing the portal list directly, a citizen can describe what
   they need in their own words via `POST /api/v1/conversation/message`
   (`system_orchestrator` proxying to `intent_service`, Phase C1-C4). Once
   the conversation resolves a single service, its `service_id` feeds
   straight into step 5 below via the existing `POST /api/v1/portals/confirm`
   — no new model, no separate redirect path.
2. **Upload** — an applicant's document is hashed client-side and stored via
   `system_orchestrator/app` (`POST /api/v1/documents`).
3. **Validate** (Phase 1) — the document is checked against the supported
   type catalog, metadata limits, and OCR-text sanity via
   `input_validation_security_engine` (`POST /api/v1/validate`), including a
   non-authoritative eligibility pre-check.
4. **Guide / extract** (Phase 2) — validated documents go to
   `ai_guidance_engine` (`POST /api/v1/extract`), which returns structured
   fields with a confidence score, source document, and reasoning, via a
   provider-independent LLM abstraction.
5. **Govern** (Phase 4) — the extracted fields are handed to
   `trust_governance_engine` (`POST /api/v1/applications`), where a human
   caseworker approves, rejects, or edits each field. Once every field is
   decided, an OTP gates final submission (`POST /api/v1/submit`) — and if
   an applicant has named a Trusted Delegate (Phase F, `POST
   /api/v1/applications/{id}/delegate`) with `approval_required: true`,
   their approval gates it too, on top of OTP, never instead of it.
   Submission locks the application. Every step — field decisions, OTP
   events, delegate registration/approval, and the submission itself — is
   written to an immutable, hash-chained audit log, and CSV/JSON/PDF
   reports can be generated on demand.
6. **Redirect safely** (Phase D) — whenever `system_orchestrator` is about
   to hand a citizen off to an official site (`POST /api/v1/portals/confirm`),
   it first calls `risk_engine` (`POST /api/v1/risk/redirect-check`) to
   verify HTTPS and the official domain whitelist (sourced live from
   `official_service_registry`). A failed check blocks the redirect with
   `409` instead of proceeding.

The Multilingual Guidance UI (Phase 3) is the one place all of this is wired
together end-to-end: section 3 ("Ask Sahaay.AI") can hand a resolved service
straight into the same confirm/redirect flow section 4's portal cards use,
and section 5 ("AI Field Extraction") can hand its result straight to
section 6 ("Human Review & Governance") with one click.

## Design principles carried across every service

- **Independent, sibling services.** Same layered architecture in each
  (`api/`, `models/`, `services/`, `utils/`, sometimes `db/` or
  `providers/`), same naming conventions, own `requirements.txt`. No service
  imports code from another — only HTTP.
- **CORS enabled per-service**, defaulting to `ALLOWED_ORIGINS=*` for local
  development. Set it explicitly (comma-separated origins) before deploying
  publicly.
- **No mock logic.** Where a real integration doesn't exist yet (e.g. an
  actual SMS/e-mail provider for OTP delivery, or image OCR), the code says
  so explicitly and exposes a clean seam for it (`OTPDeliveryProvider`,
  documented client-side-only text extraction) rather than faking the
  behavior.
- **Provider independence** for the AI Guidance Engine — Gemini, OpenAI,
  Claude, Azure OpenAI, and Ollama are all pluggable without touching
  business logic.

## Not yet done

- **Security Shield (Phase D) is still minimal, not complete.** `risk_engine`
  covers exactly two signals — HTTPS/domain-whitelist verification and
  sensitive-field (OTP/password/PIN/CVV) label detection. There is no live
  browser/DOM monitoring and no heuristic phishing-page scoring (visual
  similarity, typosquatting distance). `ai_guidance_engine` now does call
  `risk_engine`'s content-scan (on AI-extracted field text, before it's
  returned — see `ExtractionService._scan_fields_for_risk`), so both the
  redirect path (`system_orchestrator`) and the extraction path
  (`ai_guidance_engine`) are wired in; note `ai_guidance_engine` still
  doesn't generate free-text "guidance step" narration the way the Phase E
  brief eventually describes — today it's field extraction, not a
  screen-by-screen walkthrough, so there's no such text to scan yet beyond
  the extracted field values/reasons themselves.
- **Trusted Delegate (Phase F) covers register/approve/revoke, gates
  submission, and now notifies on every event** via a pluggable
  `DelegateNotificationProvider` (default: log-only, same gap as OTP
  delivery — no real SMS/e-mail send exists anywhere in this codebase to
  hang a real one off yet). It still does not include a UI flow for the
  delegate to review the application's fields themselves before approving
  (today `approve` just records a yes/no from whoever has the link).
- **Phase C is C1–C4 complete, C5 not started.** Text-only intent
  classification (C1), Official Service Directory lookup + ranking (C2),
  multilingual support (C3 — offline script-based language detection plus
  per-language keyword taxonomies for English, Hindi, Marathi, Bengali,
  Tamil, and Telugu), and multi-turn conversation/context management (C4 —
  disambiguation, missing-field follow-up questions, autofill, eligibility
  resolution) are all complete in `intent_service/`, and were consolidated
  into one cohesive module in a follow-up pass (deduped request models and
  registry-client construction between C2/C4, plus a new
  `tests/test_phase_c_integration.py` end-to-end suite — see
  `intent_service/README.md`'s "Phase C consolidation" section). C5
  (voice/STT) is not implemented yet — see "Phase C roadmap" above. C2/C3's
  ranking is word-overlap, not semantic (no embeddings/synonyms), and C3
  detects/classifies in the citizen's language but does not translate
  service names, descriptions, or match reasons (those stay in whatever
  language `official_service_registry` authored them in — English today).
  `intent_service` itself is unmodified by this integration — it is still
  reachable directly too, at `POST /api/v1/intent/classify`, `POST
  /api/v1/intent/resolve`, and `POST /api/v1/conversation/message` — but as
  of the conversational guidance integration, `system_orchestrator` now
  proxies `/api/v1/conversation/*` to it (`system_orchestrator/app/services/intent_client.py`),
  and `multilingual_guidance_ui`'s new "3. Ask Sahaay.AI" section calls that
  proxy, so a completed conversation's `resolved_service.service_id` does
  now feed into the guidance flow via the existing portal-confirm step —
  see "Conversational guidance integration" above. C5 (voice/STT) is still
  not implemented.
- `multilingual_guidance_ui` now has a Trusted Delegate panel (register /
  load / approve / revoke, with live status) inside the Human Review &
  Governance section, and renders the Security Shield's 409 pause as a
  distinct panel with every finding listed, instead of a generic error
  string.
- No bulk/list view across applications, and no auth/session handling
  anywhere in the UI (`applicant_id` and "Caseworker ID" are plain text
  fields — fine for a local demo, not for production).
- **Verification status (updated after Phase C3 completion).** All seven
  services' test suites were run for real in this session (`pytest`, real
  installs from PyPI — this sandbox does allow that): 125 tests total, 124
  passing. The one failure —
  `trust_governance_engine/tests/test_governance_api.py::test_trusted_delegate_events_record_notification_channel`
  — pre-dates Phase C3 (it already fails identically against the Phase C2
  snapshot) and is in a service Phase C3 never touched, so it's flagged
  here as a known pre-existing issue rather than fixed as part of this
  pass. `intent_service`'s own suite (31 tests, including the new
  `test_intent_classify_multilingual.py`) passes in full. Beyond unit
  tests, `official_service_registry` and `intent_service` were also
  booted together as real live HTTP processes and exercised with actual
  `POST /api/v1/intent/resolve` calls in English and Hindi — not just
  mocked-dependency unit tests — confirming the live cross-service call
  path works end-to-end.
- **Verification status for the Phase C consolidation pass.** This
  environment had no PyPI/network access during this pass, so the dedup
  edits and the new `test_phase_c_integration.py` file were verified by
  `python -m py_compile` across the whole `intent_service/` package (all
  files parse cleanly) plus a manual trace of every constructor signature,
  field name, and response shape the new test file depends on
  (`RegistryClient`/`IntentService`/`ServiceLookupService`/
  `InMemoryConversationStore`/`ConversationManager` constructors,
  `IntentResolveResponse`/`ConversationTurnResponse` field names, the
  `pension_application`/`banking_kyc` intent ids, and the
  `applicant_age`/`has_existing_aadhaar` field-prompt data) against the
  actual source in this repo, matching them line-for-line. It was **not**
  executed with a live `pytest` run in this pass — run
  `pytest intent_service/tests -v` locally/in CI before relying on it, the
  same as any other change to this repo.
- **Not verified in this sandbox: all seven services running
  simultaneously.** Each service was verified individually (and
  `official_service_registry` + `intent_service` together, live), but
  keeping all seven long-running `uvicorn` processes up across many tool
  calls isn't reliable in this environment — background processes here
  don't reliably survive past the tool call that started them. Before
  relying on this build, run the full `## Running everything locally`
  sequence above locally/in CI with all seven services and the UI up at
  once, and click through the Multilingual Guidance UI's existing
  Phase 1/2/4 flow end-to-end (`intent_service` isn't wired into the UI
  yet, so there's no new UI flow to click through for C3 specifically —
  see the Phase C bullet above).
- **Verification status for the conversational guidance integration pass.**
  This environment had no PyPI/network access, so `system_orchestrator`'s
  new proxy routes/tests (already present in the uploaded snapshot) and the
  new `multilingual_guidance_ui` chat section (written in this pass) were
  verified statically only: `python -m py_compile` across every
  `system_orchestrator` file, `node --check`-equivalent parsing of
  `app.js`, and HTML-parser validation of `index.html`, plus a manual trace
  of `ConversationTurnResponse`'s field names against what `app.js` reads
  and of `intent_client.py`'s method signatures against what
  `api/routes.py` calls. **Not executed with a live `pytest` run or a
  clicked-through browser session in this pass** — run
  `pytest system_orchestrator/app/tests -v` and open
  `multilingual_guidance_ui/index.html` against a real running
  `system_orchestrator` + `intent_service` before relying on this.

## Final integration & consistency review (Phases A–D)

This pass took the four phase snapshots (A "stabilized", B "complete", C
"consolidated", D "implemented") and verified/finalized them as one
cohesive build. Phase D was used as the baseline because it is a strict
superset of A, B, and C: the Phase A services live on inside it as the
backward-compatible alias packages described above, Phase B's rename and
Phase C's `intent_service` are unchanged inside it, and Phase D adds the
`system_orchestrator` ↔ `intent_service` wiring on top. No phase's work was
dropped or overwritten in this pass.

**What was checked, with this environment's real PyPI access:**
- Repo-wide `python -m py_compile` across every `.py` file — all compile
  cleanly.
- All 7 live services (`system_orchestrator`, `ai_guidance_engine`,
  `input_validation_security_engine`, `trust_governance_engine`,
  `official_service_registry`, `risk_engine`, `intent_service`) share
  uniform `/api/v1` prefixing and identical `CORSMiddleware` setup.
- The 4 Phase A alias packages (`backend`, `ai_extraction_engine`,
  `document_validation_engine`, `governance_engine`) import correctly and
  resolve to their renamed Phase B targets — confirmed with a live
  `import`, not just a source read.
- Every service's `.env.example` documents every variable its `config.py`
  actually reads, including the Phase D additions
  (`INTENT_SERVICE_BASE_URL`, `INTENT_SERVICE_TIMEOUT_SECONDS`).
- No duplicated eligibility logic: `input_validation_security_engine` and
  `intent_service` both delegate to `official_service_registry`'s single
  `eligibility_engine` over HTTP rather than re-implementing rules.
- The full repo test suite was run for real: **175/175 tests pass**
  (`system_orchestrator`, `intent_service`, `ai_guidance_engine`,
  `input_validation_security_engine`, `trust_governance_engine`,
  `official_service_registry`, `risk_engine` combined, single `pytest`
  invocation, no conftest collisions).

**Fixes made in this pass (no other logic touched):**
1. `ai_guidance_engine/config.py` + `.env.example` — `RISK_ENGINE_BASE_URL`
   default was `http://localhost:8005`, inconsistent with every other
   service's `http://127.0.0.1:...` inter-service default. Corrected to
   `127.0.0.1`.
2. `trust_governance_engine/tests/test_governance_api.py` — a test bug:
   `test_trusted_delegate_events_record_notification_channel` compared
   audit-log actions against uppercase enum *names*
   (`"TRUSTED_DELEGATE_REGISTERED"`) instead of the lowercase `.value` the
   API actually serializes (`"trusted_delegate_registered"`), inconsistent
   with every other action assertion in the same file. Corrected the
   expected strings; no production code changed.

**Sandbox-only limitations (not code defects):** this pass's `pytest` run
initially showed 2 failures in `trust_governance_engine`; one was the test
bug above, the other was `ModuleNotFoundError: No module named 'fpdf'`
purely because `fpdf2` wasn't yet installed in this sandbox session (it is
correctly listed in `trust_governance_engine/requirements.txt` already) —
installing it made the PDF-report test pass with no code change. Running
all 7 services simultaneously as long-lived background processes and
clicking through the UI live was not exercised in this sandbox for the
same reason noted in the bullets above (background processes don't
reliably survive across tool calls here); every service's own test suite
and the cross-service HTTP contracts were verified instead. Before a live
demo, run `## Running everything locally` below with all 7 services and
the UI up at once as a final smoke test — no issues are expected given the
contract-level verification above, but it hasn't been clicked through
end-to-end inside this sandbox.

**Verdict: integration-complete and demo-ready**, with the one caveat
above (live simultaneous-services smoke test not run in-sandbox). No
Phase E/F work was started, and no new features were added — this pass was
strictly finalize-and-validate.
