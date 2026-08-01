import os
import sys

if __package__ in (None, ""):
    # Support running this module standalone, e.g.
    # `cd input_validation_security_engine && uvicorn app:app --port 8001`.
    # In that mode Python loads this file as a top-level module with no
    # parent package, so the relative imports below (`from .config import
    # ...`) would normally fail with "attempted relative import with no
    # known parent package". Registering the repo root on sys.path and
    # setting __package__ before those imports run lets Python resolve them
    # against the real input_validation_security_engine package instead, without
    # changing any of the import statements themselves. This also keeps the
    # package-style invocation (`python -m input_validation_security_engine.app`,
    # or `from input_validation_security_engine.app import app`) working exactly
    # as before, since __package__ is already set in that case and this
    # block is skipped.
    _PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)
    __package__ = "input_validation_security_engine"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router
from .config import settings
from .utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Input Validation & Security Engine",
    version="1.0.0",
    description=(
        "Independent input validation & security microservice for Sahaay.AI "
        "(formerly the Document Validation Engine)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS: this microservice is called directly by the browser-based frontend
# (multilingual_guidance_ui/app.js -> VALIDATION_BASE), so it needs its own
# CORS policy, same as system_orchestrator/app.main already does for the
# primary backend.
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
        "engine": "Input Validation & Security Engine",
        "message": "Use /api/v1/validate for document validation or /health for readiness.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "Input Validation & Security Engine"}


if __name__ == "__main__":
    import uvicorn

    # Both invocation styles work: `python -m input_validation_security_engine.app`
    # from the repo root, or `cd input_validation_security_engine && uvicorn
    # app:app --port 8001` (the PEP 366 bootstrap above makes the relative
    # imports resolve correctly either way).
    uvicorn.run("input_validation_security_engine.app:app", host="0.0.0.0", port=8001, reload=False)
