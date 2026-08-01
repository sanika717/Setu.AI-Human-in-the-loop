import os
import sys

if __package__ in (None, ""):
    # Support running this module standalone, e.g.
    # `cd trust_governance_engine && uvicorn app:app --port 8003`.
    # In that mode Python loads this file as a top-level module with no
    # parent package, so the relative imports below (`from .config import
    # ...`) would normally fail with "attempted relative import with no
    # known parent package". Registering the repo root on sys.path and
    # setting __package__ before those imports run lets Python resolve them
    # against the real trust_governance_engine package instead, without changing
    # any of the import statements themselves. This also keeps the
    # package-style invocation (`python -m trust_governance_engine.app`, or
    # `from trust_governance_engine.app import app`) working exactly as before,
    # since __package__ is already set in that case and this block is
    # skipped.
    _PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)
    __package__ = "trust_governance_engine"

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import settings
from .db.models import Base
from .db.session import engine
from .utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Trust & Governance Engine",
    version="1.0.0",
    description=(
        "Independent Phase 4 microservice for Sahaay.AI (formerly the Human "
        "Decision & Governance Engine): approve/reject/edit extracted fields, "
        "OTP-gated final submission, immutable audit logging, and report "
        "generation (CSV/JSON/PDF)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS: this microservice is called directly by the browser-based frontend,
# same as input_validation_security_engine and ai_guidance_engine.
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
        "engine": "Trust & Governance Engine",
        "message": "Use /api/v1/applications for the review workflow or /health for readiness.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "Trust & Governance Engine"}


if __name__ == "__main__":
    import uvicorn

    # system_orchestrator/app (8000), input_validation_security_engine
    # (8001), and ai_guidance_engine (8002) also run locally at the same time
    # during integration testing, so this service defaults to 8003.
    #
    # Both invocation styles work: `python -m trust_governance_engine.app` from
    # the repo root, or `cd trust_governance_engine && uvicorn app:app --port
    # 8003` (the PEP 366 bootstrap above makes the relative imports resolve
    # correctly either way).
    uvicorn.run("trust_governance_engine.app:app", host="0.0.0.0", port=8003, reload=False)
