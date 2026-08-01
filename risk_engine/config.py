import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Risk Engine")
    api_version: str = os.getenv("API_VERSION", "v1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    allowed_origins: list[str] = field(default_factory=lambda: _env_list("ALLOWED_ORIGINS", ["*"]))

    # Official Service Registry (official_service_registry) - source of truth
    # for each service's official_url + allowed_domains whitelist. This
    # engine calls it live for every redirect check rather than keeping its
    # own copy, so a domain change in services.json takes effect here
    # immediately with no redeploy.
    registry_base_url: str = os.getenv("REGISTRY_BASE_URL", "http://127.0.0.1:8004")
    registry_timeout_seconds: float = _env_float("REGISTRY_TIMEOUT_SECONDS", 5.0)


settings = Settings()
