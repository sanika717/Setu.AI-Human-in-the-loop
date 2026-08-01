import os
import sys

if __package__ in (None, ""):
    # Support running this module standalone, e.g.
    # `cd official_service_registry && uvicorn app:app --port 8004`.
    _PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PKG_ROOT not in sys.path:
        sys.path.insert(0, _PKG_ROOT)
    __package__ = "official_service_registry"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router
from .config import settings
from .utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Official Service Registry",
    version="1.0.0",
    description=(
        "Config-driven catalog of every official government/banking service "
        "Sahaay.AI can guide a user through - service names, official "
        "URLs/domains, required documents, eligibility rules, workflow "
        "steps, and supported languages. Adding a new service is a data "
        "change to services.json, never a code change."
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
        "engine": "Official Service Registry",
        "message": "Use /api/v1/services for the service catalog or /health for readiness.",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "Official Service Registry"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("official_service_registry.app:app", host="0.0.0.0", port=8004, reload=False)
