# Intent Service (Phase C: Intent & Service Discovery)

Independent FastAPI microservice. Stateless — no database, no external API
calls. Given free-form citizen text, it classifies the request into one of
a fixed set of intents using a hand-authored, per-language keyword taxonomy.

Delivered incrementally so each milestone can be built, tested, and shipped
independently before the next one starts:

| Sub-phase | Scope | Status |
|---|---|---|
| **C1** | Text-only intent classification, modular classifier design | Done |
| **C2** | Official Service Directory lookup: intent → `official_service_registry` service_id, with ranking/confidence | Done |
| **C3** | Multilingual support: language detection, localized intent taxonomies | Done |
| **C4 (this update)** | Conversation/context management: follow-ups, missing-information prompts | Done |
| C5 (optional) | Voice/STT pipeline | Not started |

## What it does today

- `POST /api/v1/intent/classify` — takes
  `{"text": "...", "applicant_id": "...", "language": "..."}` (both
  `applicant_id` and `language` are optional) and returns:
  - `detected_intent` — one of the intent IDs in `data/intents.json` (or its
    per-language counterpart, e.g. `data/intents_hi.json`), or
    `"unclassified"` if nothing cleared the minimum-confidence threshold,
    or the language isn't supported.
  - `confidence` / `confidence_level` / `alternate_intents` — same shape and
    meaning as Phase C1, computed against whichever language's taxonomy was
    used.
  - `language`, `language_name` — the ISO 639-1 code and display name the
    request was actually classified in.
  - `language_source` — `"declared"` if the caller passed `language` on the
    request, else `"detected"`.
  - `language_detection_confidence` — `1.0` when declared (the caller's
    word is authoritative); otherwise the script-detector's confidence.
  - `language_supported` — `false` if no keyword taxonomy exists yet for
    the resolved language. When `false`, `detected_intent` is always
    `"unclassified"`.

- `POST /api/v1/intent/resolve` — same request shape as `/classify`, plus
  the same `language`/`language_name`/`language_source`/
  `language_detection_confidence`/`language_supported` fields as `/classify`.
  Classifies the text exactly as `/classify` does, then (if the detected
  intent has a `service_category_hint`) calls `official_service_registry`'s
  `GET /api/v1/services`, filters to that category, **prefers services that
  declare support for the resolved language** (falling back to the full
  category list — with a note explaining why — if none do), and ranks the
  remaining candidates by word-overlap between the request text and each
  service's name/description/service_id. Returns:
  - `service_category` — the category searched, or `null` if the intent
    has none (e.g. a greeting), was unclassified, or the language isn't
    supported.
  - `matches` — up to `INTENT_MAX_SERVICE_MATCHES` (default 3) ranked
    `ServiceMatch` entries, each with `match_confidence` and a
    human-readable `match_reason`.
  - `registry_available` — `false` if `official_service_registry` couldn't
    be reached; `/resolve` still returns 200 with an empty `matches` list
    and an explanatory `resolution_note` rather than failing.

## Multilingual support (Phase C3)

Supported languages today: **English (en), Hindi (hi), Marathi (mr),
Bengali (bn), Tamil (ta), Telugu (te)** — the same set
`official_service_registry/data/services.json`'s `supported_languages`
values already use.

- **Language detection** (`providers/language_detector.py`) is fully
  offline and deterministic: it counts Unicode script-block codepoints
  (Devanagari, Bengali, Tamil, Telugu, or Latin) and picks the dominant
  script. No model, no network call, no external dependency — the same
  principle the keyword classifier itself follows. Devanagari is shared by
  Hindi and Marathi, so it's further disambiguated by checking for a small
  set of common Marathi function words/verb forms (e.g. "आहे"/"आहेत",
  the possessive suffixes "चा"/"ची"/"चे") that don't occur, or occur far
  less often, in Hindi; any hit tips the result to Marathi, otherwise
  Devanagari defaults to Hindi.
- **Declaring a language explicitly** (`"language": "hi"` on the request)
  skips detection entirely and is treated as authoritative — useful when
  the caller's UI already has a language selector. An unrecognized code
  (anything not in the six above) is reported as `language_supported:
  false` rather than guessed at.
- **Per-language taxonomies**: `data/intents_hi.json`, `intents_mr.json`,
  `intents_bn.json`, `intents_ta.json`, `intents_te.json` mirror
  `data/intents.json`'s exact `intent_id`/`label`/`service_category_hint`
  structure — only the keyword phrases and weights are localized — so
  `intent_category_map.py` and every downstream consumer of
  `detected_intent` keeps working unchanged regardless of which language
  classified the request.
- **Unicode-safe matching**: keyword matching normalizes text by keeping
  every Unicode letter/mark/number character (not just `\w`, which
  excludes combining marks like Devanagari/Bengali/Tamil/Telugu vowel
  signs) and uses whitespace-anchored word boundaries instead of regex's
  `\b` (which is defined via `\w` transitions and would silently fail
  right after a phrase ending in a combining mark, e.g. Hindi "केवाईसी").
- **`providers/factory.create_classifier_for_language(language)`** builds a
  `KeywordIntentClassifier` for a given language's taxonomy, or returns
  `None` if that language isn't supported yet — the single place a future
  seventh language gets wired in.

## How classification works

`providers/keyword_classifier.py` scores the (lowercased, punctuation-
stripped, Unicode-normalized) input text against the resolved language's
taxonomy file: each intent is a list of keyword phrases with a weight, and
an intent's raw score is the sum of the weights of every phrase found in
the text, matched on word boundaries (so `"pan"` doesn't match inside
`"expansion"`, in any language). `services/intent_service.py` then
normalizes those raw scores into confidences (each intent's score divided
by the total across all intents that matched) and applies
`INTENT_MIN_CONFIDENCE` (default `0.2`) — below that, the result is
reported as `"unclassified"` rather than guessed at.

Adding or improving an intent is a **data change, not a code change** — edit
`data/intents.json` (English) or the relevant `data/intents_<code>.json`.
Adding a seventh language means: add a script range (if it's a new script)
or marker-word check (if it's a new language sharing an existing script) to
`providers/language_detector.py`, add `data/intents_<code>.json`, and
register both in `providers/keyword_classifier.py`'s
`LANGUAGE_TAXONOMY_FILES`. Nothing else in the service needs to change —
`IntentService`, the API routes, and `ServiceLookupService` are all
language-agnostic by construction.

## What it deliberately does NOT do yet

- **Ranking is word-overlap, not semantic.** `/intent/resolve` matches
  literal shared words (after stripping common ones like "for"/"my"/"the")
  between the request text and each service's name/description/service_id.
  It has no embedding model or synonym awareness. Good enough as a first,
  fully-offline pass; a semantic ranker is a reasonable future improvement.
- **No translation.** Phase C3 detects and classifies in the citizen's
  language; it does not translate `label`s, `match_reason`s, or service
  names/descriptions (those stay in whatever language they were authored
  in — English for `official_service_registry` today). Localizing
  human-facing strings is future guidance-layer work, not intent
  classification.
- **No conversational memory.** Every call to `/intent/classify` or
  `/intent/resolve` is evaluated independently; there's no session state,
  no follow-up question handling for missing information. That's Phase C4.
- **No voice/audio input.** Text only. That's the optional Phase C5.
- **Not yet wired into `system_orchestrator` or the UI.** Both endpoints
  are reachable and independently testable today, but nothing in the
  existing guidance flow calls them yet.

## Run it

```bash
pip install -r intent_service/requirements.txt
cp intent_service/.env.example intent_service/.env   # edit if needed
uvicorn intent_service.app:app --reload --port 8006   # from the repo root
```

(Or `cd intent_service && uvicorn app:app --reload --port 8006` — the same
PEP 366 bootstrap used by the other services makes both invocations work.)

`POST /intent/classify` has zero inter-service dependencies. `POST
/intent/resolve` additionally calls `official_service_registry` (default
`http://127.0.0.1:8004`) to fetch the service catalog to rank against; if
that service isn't running, `/resolve` still returns 200 with
`registry_available: false` rather than failing.

## Tests

```bash
pytest intent_service/tests -v
```

- `test_intent_api.py` — Phase C1, `/intent/classify` end-to-end, English.
- `test_intent_resolve_api.py` — Phase C2 `/intent/resolve` coverage, plus
  Phase C3 multilingual resolve cases (auto-detected Hindi, language-aware
  registry filtering and its fallback, unsupported declared language,
  declared-overrides-detected precedence) — all via a `RegistryClient` test
  double + FastAPI dependency override, so nothing here needs a live
  registry process.
- `test_intent_classify_multilingual.py` — Phase C3, `/intent/classify`
  across all six supported languages, Hindi-vs-Marathi disambiguation,
  declared-language override (including an unrecognized code and a
  case/whitespace-insensitive code), and cross-language confidence-level
  sanity checks.

## Example

```bash
curl -X POST http://127.0.0.1:8006/api/v1/intent/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है"}'
```

```json
{
  "engine": "Intent Service",
  "provider": "Keyword",
  "text": "मुझे वृद्धावस्था पेंशन के लिए आवेदन करना है",
  "language": "hi",
  "language_name": "Hindi",
  "language_source": "detected",
  "language_detection_confidence": 1.0,
  "language_supported": true,
  "detected_intent": "pension_application",
  "label": "Apply for a pension",
  "confidence": 1.0,
  "confidence_level": "High",
  "alternate_intents": []
}
```

```bash
curl -X POST http://127.0.0.1:8006/api/v1/intent/resolve \
  -H "Content-Type: application/json" \
  -d '{"text": "I want to apply for old age pension"}'
```

```json
{
  "engine": "Intent Service",
  "text": "I want to apply for old age pension",
  "language": "en",
  "language_name": "English",
  "language_source": "detected",
  "language_detection_confidence": 1.0,
  "language_supported": true,
  "detected_intent": "pension_application",
  "label": "Apply for a pension",
  "confidence": 1.0,
  "confidence_level": "High",
  "service_category": "pension",
  "matches": [
    {
      "service_id": "nsap_old_age_pension",
      "service_name": "National Social Assistance Programme - Old Age Pension",
      "category": "pension",
      "description": "Monthly pension for elderly citizens under India's National Social Assistance Programme.",
      "official_url": "https://nsap.nic.in",
      "match_confidence": 0.5,
      "match_reason": "Matched on: age, old, pension"
    },
    {
      "service_id": "nsap_widow_pension",
      "service_name": "National Social Assistance Programme - Widow Pension",
      "category": "pension",
      "description": "Monthly pension for widows under India's National Social Assistance Programme.",
      "official_url": "https://nsap.nic.in",
      "match_confidence": 0.1667,
      "match_reason": "Matched on: pension"
    },
    {
      "service_id": "nsap_disability_pension",
      "service_name": "National Social Assistance Programme - Disability Pension",
      "category": "pension",
      "description": "Monthly pension for persons with disabilities under India's National Social Assistance Programme.",
      "official_url": "https://nsap.nic.in",
      "match_confidence": 0.1667,
      "match_reason": "Matched on: pension"
    }
  ],
  "registry_available": true,
  "resolution_note": ""
}
```

## Phase C4: Conversation & Context Management

Adds a modular, multi-turn **conversation layer** on top of C1/C2/C3,
without changing `/intent/classify` or `/intent/resolve` in any way. It is
a new set of files (models, a store, a manager, routes) that *composes*
`IntentService` and `ServiceLookupService` rather than editing them.

### What it does

1. **Maintains context across turns.** Each conversation gets a
   `conversation_id` (generated on the first message, passed back by the
   caller on every following one). Everything gathered so far —
   detected intent, resolved service, collected eligibility answers,
   attempt counters, language — lives in a `ConversationSession` on the
   server side, keyed by that id.
2. **Detects incomplete requests.** Once a service is resolved (via the
   same C2 `/intent/resolve` ranking logic), its `eligibility_rules` from
   `official_service_registry` are read to see which fields are still
   missing from `collected_context`.
3. **Asks only for what's missing**, one field at a time, using a
   data-driven question — an authored translation from
   `data/field_prompts.json` if one exists for that field/language, else a
   generic question built from the field name and its inferred type
   (boolean/numeric/string, inferred purely from the rule's
   `operator`/`value` — no field-name-specific code).
4. **Never asks the same thing twice.** A field already present in
   `collected_context` — whether the citizen stated it explicitly or it
   was opportunistically autofilled from their very first message (e.g.
   *"I am 65 and want old age pension"* fills `applicant_age` without a
   follow-up question) — is skipped.
5. **Resumes automatically.** The instant no fields remain missing, the
   conversation calls the registry's `POST /services/{id}/eligibility`
   itself and returns the result — no separate "finalize" call needed.

### New conversation states

`collecting_intent → disambiguating_service → collecting_info → completed`,
with a `needs_human_help` terminal state reached only after repeated
unclassifiable input or repeated unresolved disambiguation. `completed`
and `needs_human_help` are terminal — sending another message to that
`conversation_id` returns a message saying so rather than reopening it;
start a new conversation (omit `conversation_id`) instead.

The conversation layer never hard-fails: an unreachable registry, an
unparseable answer, an ambiguous service pick, or unclassifiable text all
degrade gracefully (a clarifying question, a graceful fallback pick after
`CONVERSATION_MAX_DISAMBIGUATION_ATTEMPTS`, a field recorded as unknown
after `CONVERSATION_MAX_FIELD_ATTEMPTS`) instead of ever returning a 5xx.

### New endpoints

- `POST /api/v1/conversation/message` — send one turn.
  Request: `{"conversation_id": null, "text": "...", "language": "...", "applicant_id": "..."}`
  (`conversation_id`, `language`, `applicant_id` are all optional — omit
  `conversation_id` to start a new conversation).
  Response (`ConversationTurnResponse`): `conversation_id`, `state`,
  `turn_count`, `message` (what to show the citizen next), `language`,
  `detected_intent`, `candidate_matches` (while disambiguating),
  `resolved_service`, `collected_context`, `missing_fields`,
  `pending_field`, `eligibility_result`, `is_complete`,
  `registry_available`, `notes`.
- `GET /api/v1/conversation/{conversation_id}` — read-only snapshot of the
  current state; does not advance the conversation or ask a new question.
  404 if the id doesn't exist (or its session has expired).
- `DELETE /api/v1/conversation/{conversation_id}` — discards a
  conversation's state. Not required between conversations (idle sessions
  expire on their own after `CONVERSATION_SESSION_TTL_SECONDS`), but
  useful to explicitly restart. 404 if the id doesn't exist.

### Example flow

```bash
curl -X POST http://127.0.0.1:8006/api/v1/conversation/message \
  -H "Content-Type: application/json" \
  -d '{"text": "I want to apply for old age pension"}'
```

```json
{
  "engine": "Intent Service",
  "conversation_id": "b1c2...e9",
  "state": "collecting_info",
  "turn_count": 1,
  "message": "What is your age?",
  "language": "en",
  "language_name": "English",
  "detected_intent": "pension_application",
  "resolved_service": {
    "service_id": "nsap_old_age_pension",
    "service_name": "National Social Assistance Programme - Old Age Pension",
    "official_url": "https://nsap.nic.in"
  },
  "collected_context": {},
  "missing_fields": ["applicant_age"],
  "pending_field": "applicant_age",
  "is_complete": false,
  "registry_available": true
}
```

```bash
curl -X POST http://127.0.0.1:8006/api/v1/conversation/message \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "b1c2...e9", "text": "65"}'
```

```json
{
  "conversation_id": "b1c2...e9",
  "state": "completed",
  "turn_count": 2,
  "message": "Thanks - here's what I found for National Social Assistance Programme - Old Age Pension: Must be at least 60. You'll be guided to the official site at https://nsap.nic.in next. Sahaay.AI never asks for your password, OTP, or PIN.",
  "collected_context": {"applicant_age": 65},
  "missing_fields": [],
  "eligibility_result": {
    "service_id": "nsap_old_age_pension",
    "is_eligible": true,
    "rule_results": [
      {"field": "applicant_age", "operator": "gte", "passed": true, "message": "Must be at least 60."}
    ]
  },
  "is_complete": true
}
```

If a request is ambiguous (e.g. *"I want to apply for pension"* with
several matching pension services and no clear winner), the response
comes back in `disambiguating_service` state with a numbered
`candidate_matches` list; reply with the number or the service's name to
pick one.

### Multilingual behavior (builds on C3)

Language is auto-detected the same way `/intent/classify` does on the
first turn. Once a language is established for a conversation, it is
**reused for every later turn** rather than re-detected — a bare numeric
reply like `"65"` carries no script information at all, so re-detecting it
would incorrectly reset the session back to English. An explicit
`language` override on any request is still honored. Follow-up questions
and system messages (clarification prompts, disambiguation prompts, retry
text) are looked up from `data/field_prompts.json` /
`data/conversation_messages.json` for the resolved language, falling back
to English when no translation exists yet — adding a language is a data
change, not a code change.

### New files (all additive — nothing from C1/C2/C3 was modified except
purely-additive extensions noted below)

```
intent_service/
  models/conversation_models.py       # ConversationState, request/response contracts
  services/conversation_store.py      # ConversationSession + pluggable ConversationStore
                                       #   (InMemoryConversationStore is the default; the
                                       #   Protocol is the seam a Redis-backed store plugs
                                       #   into later without touching the manager or API)
  services/conversation_manager.py    # The state machine itself
  services/field_prompt_service.py    # Loads/serves data/field_prompts.json,
                                       #   data/conversation_messages.json, data/answer_lexicon.json
  services/answer_parser.py           # Infers field type from an eligibility rule and
                                       #   parses free-text answers (boolean/numeric/string),
                                       #   including Devanagari/Bengali/Tamil/Telugu digits
  data/field_prompts.json             # Per-field, per-language follow-up questions
  data/conversation_messages.json     # System-authored conversation messages, per language
  data/answer_lexicon.json            # Multilingual yes/no word lists
  api/conversation_routes.py          # POST/GET/DELETE /api/v1/conversation/*
  tests/test_conversation_manager.py  # Unit tests against a fake registry client
  tests/test_conversation_api.py      # API-level integration tests
  tests/test_phase_c_integration.py   # Phase C consolidation: C1+C2+C3+C4 as one flow

# Purely-additive extensions to existing files (no existing line changed):
  services/registry_client.py         # + get_service(), + check_eligibility()
                                       #   (existing list_services() untouched)
  api/dependencies.py                 # + get_conversation_manager()
  config.py                           # + 5 new Settings fields (all env-var-driven)
  app.py                              # + include_router(conversation_router, ...),
                                       #   description/root-message text updated

# Phase C consolidation pass (dedup, no behavior/contract change):
  models/conversation_models.py       # ConversationMessageRequest now extends
                                       #   IntentClassifyRequest instead of
                                       #   re-declaring text/applicant_id/language
  api/dependencies.py                 # get_conversation_manager() now builds one
                                       #   RegistryClient and shares it with the
                                       #   ServiceLookupService it constructs,
                                       #   instead of building two separate clients
```

### New settings (all in `config.py` / `.env.example`, all env-var-configurable)

| Env var | Default | Meaning |
|---|---|---|
| `CONVERSATION_SESSION_TTL_SECONDS` | `1800.0` | How long an idle session is kept before it's dropped |
| `CONVERSATION_MAX_CLARIFICATION_ATTEMPTS` | `3` | Retries before `needs_human_help` on unclassifiable input |
| `CONVERSATION_MAX_DISAMBIGUATION_ATTEMPTS` | `3` | Retries before auto-picking the top disambiguation candidate |
| `CONVERSATION_MAX_FIELD_ATTEMPTS` | `3` | Retries before recording a field as unknown and moving on |
| `CONVERSATION_DISAMBIGUATION_CONFIDENCE_GAP` | `0.34` | Min. lead the top candidate needs over the runner-up to skip disambiguation |

### Design notes / ready for C5 (voice)

`ConversationManager.handle_message()` takes plain text plus an optional
language code — exactly what `/intent/classify` already takes. A future
voice layer only needs to transcribe audio to text and call
`handle_message()` with the result; nothing in the conversation layer's
contracts assumes the input came from typing.

### Running the Phase C4 tests

```bash
pip install -r requirements.txt   # now includes pytest-asyncio
pytest tests/test_conversation_manager.py tests/test_conversation_api.py -v
```

`test_conversation_manager.py` exercises `ConversationManager` directly
against a `FakeRegistryClient` test double (no live registry needed) and
covers: single-match completion with/without eligibility rules,
below-threshold ineligibility, autofill from the first message,
disambiguation by number/name/fallback, the clarification →
`needs_human_help` escalation and its terminal behavior, boolean field
parsing (yes/no), unparseable-answer retry-then-skip, duplicate-question
avoidance, conversation id stability, an unknown id starting a fresh
conversation, language stickiness across a bare-numeric follow-up,
`completed` terminality, graceful degradation when the registry is
unavailable, and `get_state()`/`reset()`. `test_conversation_api.py`
exercises the same flows through the actual HTTP routes.

## Phase C consolidation: C1 + C2 + C3 + C4 as one module

Phases C1-C4 were originally built and delivered incrementally, one zip per
phase. This pass folds them into a single, cohesive module with no
duplicated logic between phases and one end-to-end test suite proving they
actually compose correctly, rather than four features that merely coexist
in the same package.

### What changed

1. **`ConversationMessageRequest` now extends `IntentClassifyRequest`**
   (`models/conversation_models.py`) instead of re-declaring `text` /
   `applicant_id` / `language`. C4's request contract was byte-for-byte
   identical to C1's plus one new field (`conversation_id`); inheriting
   means the two can never silently drift apart as either evolves.
2. **One `RegistryClient` per request, shared by C2 and C4**
   (`api/dependencies.get_conversation_manager`). Previously this factory
   built a `ServiceLookupService` (with its own `RegistryClient`) and then
   built a *second*, separate `RegistryClient` for the `ConversationManager`
   itself — two HTTP clients pointed at the exact same
   `registry_base_url` for the same request. Now a single client is built
   and passed to both.
3. **`tests/test_phase_c_integration.py`** — new, see below. Every other
   test file is unchanged; this one is purely additive.
4. **This README section.** No other documentation changed — the
   per-phase sections above (`Multilingual support (Phase C3)`,
   `Phase C4: Conversation & Context Management`, etc.) remain accurate
   and are left as the authoritative per-phase reference.

Nothing about `/intent/classify` or `/intent/resolve`'s request/response
*shapes* changed, and no endpoint was renamed or removed — see
"Backward compatibility" below.

### Verifying C1→C2→C3→C4 work as one flow

`tests/test_phase_c_integration.py` is the new deliverable for this pass.
Unlike the per-phase files above (each of which exercises one phase's
endpoint in isolation against its own fixtures), it drives all four phases
together through the real HTTP API and asserts they *agree with each
other*, not just that each responds:

| # | What it proves | How |
|---|---|---|
| 1 | C1→C2 data flow | `/intent/classify` and `/intent/resolve` return the identical `detected_intent`/`confidence`/`language` for the same text — C2 doesn't reclassify differently than C1. |
| 2 | C3 applies uniformly | Hindi auto-detection and an explicit `language` override produce the same `language`/`language_name` whether the call goes through `/intent/classify`, `/intent/resolve`, or `/conversation/message`. |
| 3 | C4 composes C2, doesn't duplicate it | A conversation's first-turn `resolved_service`/`detected_intent`/`service_category`, and its `candidate_matches` during disambiguation, are asserted equal to what a standalone `/intent/resolve` call returns for the same text — proving `ConversationManager` calls `ServiceLookupService` rather than re-implementing its ranking. |
| 4 | Full pipeline, multiple realistic shapes | Four end-to-end scenarios in one flow each: (a) unambiguous English request with one missing numeric field, resolved against a real eligibility rule; (b) ambiguous Hindi request through disambiguation to completion, checking language stays sticky; (c) a boolean eligibility field with an ineligible outcome; (d) a single message that carries enough information to autofill and complete without any follow-up question. |
| 5 | Graceful degradation is consistent | `/intent/resolve` and `/conversation/message` both set `registry_available: false` (rather than erroring) when the registry is unreachable. |
| 6 | Backward compatibility | `/intent/classify` still classifies correctly with the conversation router mounted alongside it; `/` and `/health` are unchanged in shape. |

All registry-backed cases use the same `FakeRegistryClient` pattern as the
per-phase test files (an in-memory double implementing
`list_services`/`get_service`/`check_eligibility`, wired in via
`app.dependency_overrides`) — no live `official_service_registry` process
is required to run any test in this package.

```bash
pytest intent_service/tests/test_phase_c_integration.py -v

# or the full Phase C suite, all phases together:
pytest intent_service/tests -v
```

### Backward compatibility

- `POST /api/v1/intent/classify` and `POST /api/v1/intent/resolve`: request
  and response shapes are byte-for-byte unchanged from C1/C2/C3.
- `POST /api/v1/conversation/message`, `GET /api/v1/conversation/{id}`,
  `DELETE /api/v1/conversation/{id}`: unchanged from C4 — the
  `ConversationMessageRequest` inheritance change is a refactor of *how*
  the three shared fields are declared, not a change to the JSON schema
  callers send (`text`, `applicant_id`, `language`, `conversation_id` are
  still exactly the accepted fields, same types, same optionality).
- No endpoint was renamed, removed, or given a new required field.
- Phases A and B (`official_service_registry`,
  `input_validation_security_engine`, `trust_governance_engine`,
  `ai_guidance_engine`, `system_orchestrator`, `multilingual_guidance_ui`)
  are intentionally **not** touched or integrated with `intent_service` in
  this pass — per scope, Phase C is being finalized standalone first.
