import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Anchors the default SQLite file to this package's own directory,
# regardless of the working directory the process is started from (e.g.
# `uvicorn trust_governance_engine.app:app` run from the repo root, vs the old
# `cd trust_governance_engine && uvicorn app:app`). Without this, a relative
# "./governance.db" would land wherever the process happened to be
# launched from instead of consistently inside trust_governance_engine/.
_ENGINE_DIR = Path(__file__).resolve().parent
_DEFAULT_SQLITE_PATH = _ENGINE_DIR / "governance.db"


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Trust & Governance Engine")
    api_version: str = os.getenv("API_VERSION", "v1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    allowed_origins: list[str] = field(
        default_factory=lambda: _env_list("ALLOWED_ORIGINS", ["*"])
    )

    # This engine keeps its own database (independent of system_orchestrator/app's DB),
    # per the Phase 4 requirement to be an independent module. SQLite is the
    # default for local/dev use; point DATABASE_URL at Postgres (with an
    # async driver, e.g. postgresql+asyncpg://...) for production.
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{_DEFAULT_SQLITE_PATH}"
    )

    # --- OTP settings -----------------------------------------------------
    # OTP generation, hashing, expiry and attempt-limiting are fully
    # implemented and production-ready. What is NOT implemented is an actual
    # SMS/e-mail delivery integration — there is no such provider anywhere
    # else in this codebase to hang off of. Delivery is pluggable
    # (see services/otp_service.py: OTPDeliveryProvider) so a real provider
    # can be dropped in later without touching the approve/reject/edit or
    # submission business logic.
    otp_code_length: int = _env_int("OTP_CODE_LENGTH", 6)
    otp_expiry_seconds: int = _env_int("OTP_EXPIRY_SECONDS", 300)
    otp_max_attempts: int = _env_int("OTP_MAX_ATTEMPTS", 5)
    # A pepper mixed into the OTP hash in addition to a per-challenge random
    # salt. Must be overridden via env in any non-local deployment.
    otp_hash_pepper: str = os.getenv("OTP_HASH_PEPPER", "dev-only-otp-pepper-change-me")
    # When True (the local/dev default, since there is no real delivery
    # channel configured), the generated OTP code is echoed back in the
    # /otp/request API response so the flow can be exercised end-to-end
    # without a phone/inbox. Set to False as soon as a real
    # OTPDeliveryProvider is wired in, so the code is only ever known to the
    # applicant via the real channel.
    otp_dev_mode_expose_code: bool = _env_bool("OTP_DEV_MODE_EXPOSE_CODE", True)

    # A field is treated as "required" for submission purposes unless the
    # intake payload explicitly marks it `required: false`.
    field_required_by_default: bool = _env_bool("FIELD_REQUIRED_BY_DEFAULT", True)


settings = Settings()
