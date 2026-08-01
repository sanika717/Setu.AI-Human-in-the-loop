# AI Guidance Engine

The AI Guidance Engine is an independent FastAPI microservice dedicated to extracting structured information from OCR text using an LLM provider abstraction.

## Goals
- Accept OCR text and applicant context.
- Build prompts dynamically.
- Call an LLM provider without coupling business logic to a specific vendor.
- Return structured fields with confidence, source document, and reasoning.
- Stay independent from eligibility, approval, UI, and audit workflows.

## Architecture
- API layer: FastAPI routes in `api/`
- Services: extraction orchestration, confidence scoring, prompt building, parsing, retries, and fallback
- Providers: pluggable provider abstraction for Gemini and future vendors
- Models: Pydantic request, response, and field schemas
- Utilities: logging and exception handling

## Folder Structure
```text
ai_guidance_engine/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── api/
├── services/
├── providers/
├── models/
├── utils/
├── tests/
└── sample_data/
```

## API
### POST /api/v1/extract
Request body:
```json
{
  "applicant_id": "123",
  "documents": [
    {"type": "aadhaar", "text": "OCR extracted text"},
    {"type": "income_certificate", "text": "OCR extracted text"}
  ]
}
```

Response:
```json
{
  "status": "success",
  "provider": "Gemini",
  "engine": "AI Guidance Engine",
  "fields": [
    {
      "field": "Applicant Name",
      "value": "Ramesh Patil",
      "confidence": 0.98,
      "confidence_level": "High",
      "source_document": "Aadhaar",
      "reason": "Clearly visible and matched OCR."
    }
  ]
}
```

## Provider Architecture
The service uses the provider pattern so the extraction logic never depends on any single vendor. The base class is in `providers/base_provider.py`. Five providers are implemented and fully functional: **Gemini**, **OpenAI**, **Claude (Anthropic)**, **Azure OpenAI**, and **Ollama** (local). Pick the active one with `DEFAULT_PROVIDER` (`gemini` | `openai` | `claude` | `azure` | `ollama`); business logic (`ExtractionService`, prompt building, parsing, confidence scoring) never changes based on which one is active.

Adding a new vendor means implementing `BaseProvider.extract(prompt) -> dict` and registering it in `providers/factory.py` - nothing else in the codebase changes.

### Reliability behavior
- **Retries**: `RetryService` retries transient failures (`ProviderError`, `InvalidResponseError`) with real exponential backoff (`RETRY_BACKOFF_BASE_SECONDS`, capped at `RETRY_BACKOFF_MAX_SECONDS`).
- **Fast-fail on misconfiguration**: a missing API key raises `ProviderConfigurationError`, which is *not* retried (retrying can't fix a missing key) - it goes straight to fallback.
- **Fallback**: once retries are exhausted (or a non-retryable error occurs), `FallbackService` returns a `"Manual Review Required"` field set rather than a 500, so the API always returns a usable response.

## Configuration
Set environment variables for whichever provider(s) you use before running:
```bash
# Provider selection
export DEFAULT_PROVIDER=gemini        # gemini | openai | claude | azure | ollama
export REQUEST_TIMEOUT_SECONDS=30
export MAX_RETRIES=3
export RETRY_BACKOFF_BASE_SECONDS=0.5
export RETRY_BACKOFF_MAX_SECONDS=8

# Gemini
export GEMINI_API_KEY=your_key
export GEMINI_MODEL=gemini-2.0-flash

# OpenAI
export OPENAI_API_KEY=your_key
export OPENAI_MODEL=gpt-4o-mini

# Claude
export CLAUDE_API_KEY=your_key        # or ANTHROPIC_API_KEY
export CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Azure OpenAI
export AZURE_OPENAI_API_KEY=your_key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT=your-deployment-name

# Ollama (local, no key needed)
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.1
```

## Running Locally
```bash
# from the repo root (this app.py uses relative imports, so it must be
# run as part of the ai_guidance_engine package, not from inside the
# folder itself - see the note in app.py's __main__ block)
pip install -r ai_guidance_engine/requirements.txt
uvicorn ai_guidance_engine.app:app --reload --port 8002
```

Copy `ai_guidance_engine/.env.example` to `ai_guidance_engine/.env` and
fill in whichever provider's key you're using.

## Confidence Scoring
`ConfidenceService` does not just check "was a value present" - it also scans the model's own stated `reason` for hedging language (`"illegible"`, `"blurred"`, `"possibly"`, `"best guess"`, etc.). A value accompanied by hedged reasoning is scored **Low** even though a value exists, because the model itself is signaling uncertainty. A clean value with both a source document and a non-hedged reason scores **High** (0.95); a value with only one of those scores **Medium**.

## Testing
```bash
cd ai_guidance_engine
pytest tests/ -v
```
- `test_extract_api.py` - end-to-end API test (works without any API key configured, since a missing key correctly falls back to the manual-review path)
- `test_providers.py` - all five providers: configuration-error fast paths and response parsing (network is faked, no real API calls)
- `test_retry_service.py` - backoff math, retry-vs-fast-fail decisions, exhaustion
- `test_confidence_service.py` - hedge detection and scoring tiers

## Integration Notes
This module is intentionally decoupled from frontend, authentication, eligibility checks, and approval workflows. Other modules can integrate with it through the documented REST API and Pydantic models.
