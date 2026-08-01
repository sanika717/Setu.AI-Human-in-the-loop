import os
import sys

if __package__ in (None, ""):
    # Support running this module standalone, e.g.
    # `cd intent_service && uvicorn app:app --port 8006`.
    _PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)
    __package__ = "intent_service"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.conversation_routes import router as conversation_router
from .config import settings

app = FastAPI(
    title="Intent Service",
    version="1.0.0",
    description=(
        "Phase C1+C2+C3+C4 microservice for Sahaay.AI: text-only natural-language intent "
        "classification (POST /intent/classify), ranked Official Service Registry lookup "
        "for a classified intent (POST /intent/resolve), multilingual support "
        "(English, Hindi, Marathi, Bengali, Tamil, Telugu) with offline script-based "
        "language auto-detection or an explicit `language` override on either endpoint, "
        "and a modular multi-turn conversation layer (POST /conversation/message) that "
        "asks follow-up questions for missing eligibility information and automatically "
        "resumes resolution once enough is known. No voice yet - see the Phase C roadmap "
        "in the root README. The default keyword classifier needs no external API call; "
        "/intent/resolve and the conversation layer call official_service_registry and "
        "degrade gracefully if it's unreachable."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(conversation_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "engine": "Intent Service",
        "message": (
            "Use POST /api/v1/intent/classify, /api/v1/intent/resolve, or "
            "/api/v1/conversation/message. See /health for readiness."
        ),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "Intent Service"}


if __name__ == "__main__":
    import uvicorn

    # system_orchestrator (8000), input_validation_security_engine (8001),
    # ai_guidance_engine (8002), trust_governance_engine (8003),
    # official_service_registry (8004), and risk_engine (8005) also run
    # locally at the same time during integration testing, so this service
    # defaults to 8006.
    uvicorn.run("intent_service.app:app", host="0.0.0.0", port=8006, reload=False)
