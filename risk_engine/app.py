import os
import sys

if __package__ in (None, ""):
    # Support running this module standalone, e.g.
    # `cd risk_engine && uvicorn app:app --port 8005`.
    _PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)
    __package__ = "risk_engine"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import settings

app = FastAPI(
    title="Risk Engine",
    version="1.0.0",
    description=(
        "Independent Phase D microservice for Sahaay.AI (Security Shield): verifies HTTPS + "
        "official domain whitelists (live from the Official Service Registry) before any "
        "redirect, checks redirect chains for suspicious hops, and detects sensitive-field "
        "labels (OTP/password/PIN/CVV) so guidance can pause. Stateless - no database."
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


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "engine": "Risk Engine",
        "message": "Use /api/v1/risk/redirect-check or /api/v1/risk/content-scan. See /health for readiness.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "Risk Engine"}


if __name__ == "__main__":
    import uvicorn

    # system_orchestrator (8000), input_validation_security_engine (8001),
    # ai_guidance_engine (8002), trust_governance_engine (8003), and
    # official_service_registry (8004) also run locally at the same time
    # during integration testing, so this service defaults to 8005.
    uvicorn.run("risk_engine.app:app", host="0.0.0.0", port=8005, reload=False)
