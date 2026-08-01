# Risk Engine (Phase D: Security Shield)

Independent FastAPI microservice. Stateless — no database, no persisted
state — every check is computed fresh from the request plus a live call to
the Official Service Registry (`official_service_registry`).

## What it does today

- **`POST /api/v1/risk/redirect-check`** — given a `service_id` and the
  `target_url` Sahaay.AI is about to redirect the user to (plus any already
  observed intermediate `redirect_chain` hops):
  - Verifies the target is served over HTTPS.
  - Fetches that service's `allowed_domains` whitelist live from
    `official_service_registry` and verifies the target's host is on it (or
    a subdomain of it).
  - Flags any `redirect_chain` hop that isn't HTTPS or isn't on the
    whitelist ("suspicious navigation" / "unexpected redirect" detection).
  - Returns `should_pause_guidance: true` if anything above failed, so the
    caller (`system_orchestrator`'s `/portals/confirm`, or the AI Guidance
    Engine) can stop instead of proceeding.
  - Fails closed, never open: if the registry is unreachable,
    `domain_whitelist_verified` comes back `null` / `risk_level: "unknown"`
    with a `REGISTRY_UNAVAILABLE` finding — it never silently treats an
    unverifiable domain as safe.
- **`POST /api/v1/risk/content-scan`** — given a block of guidance-step text
  (field labels/instructions, never a value a user typed), detects whether
  it's asking for an OTP, password, PIN, or CVV and returns
  `should_pause_guidance: true` if so, so guidance stops before the
  applicant is prompted to enter a credential through Sahaay.AI.

## What it deliberately does NOT do

- **No live browser/DOM monitoring.** This engine only evaluates whatever
  URL(s) and text a caller sends it — it doesn't watch a real browser
  session, inject content-security-policy headers, or intercept navigation
  itself. Wiring that up is a frontend/browser-extension concern for a
  later phase; this engine is the decision logic a consumer would call.
- **No general phishing-content classifier.** Detection here is limited to
  the two concrete, testable signals in the Phase D brief — domain
  whitelist + sensitive-field labels. It does not attempt heuristic
  phishing-page scoring (visual similarity, typosquatting distance, etc.).
  This is a real gap, not a hidden one.
- **Never receives actual credential values.** `content-scan` takes
  descriptive text, not what a user typed. No component of Sahaay.AI (this
  one included) stores or transmits passwords, OTPs, PINs, or CVVs.

## Run it

```bash
pip install -r risk_engine/requirements.txt
cp risk_engine/.env.example risk_engine/.env   # edit if needed
uvicorn risk_engine.app:app --reload --port 8005   # from the repo root
```

(Or `cd risk_engine && uvicorn app:app --reload --port 8005` — the same
PEP 366 bootstrap used by the other services makes both invocations work.)

Requires `official_service_registry` running (default
`http://127.0.0.1:8004`) for the domain-whitelist half of `redirect-check`
to return a real answer instead of `"unknown"`; `content-scan` has no
dependency on any other service.

## Tests

```bash
pytest risk_engine/tests -v
```

Registry calls are mocked via a `RegistryClient` test double + FastAPI
dependency override (`FakeRegistryClient` in `tests/test_risk_api.py`) —
tests never require a live registry process.

## Integration point

`system_orchestrator/app/api/routes.py`'s `POST /api/v1/portals/confirm`
calls this engine's `redirect-check` before returning a `redirect_url` to
the browser, and blocks the redirect (HTTP 409) if `should_pause_guidance`
comes back true. See the root `README.md` ("How a request flows through
the phases") and `system_orchestrator/app/services/risk_client.py`.
