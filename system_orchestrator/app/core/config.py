import os
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchors the default SQLite file to this package's own directory,
# regardless of the working directory the process is started from. This
# gives the backend a zero-setup local default (no Postgres server
# required) that matches the other three microservices and the "SQLite
# acceptable for local development" guidance. Point DATABASE_URL at
# Postgres (with an async driver) for production.
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///" + os.path.join(_APP_DIR, "backend_dev.db")


class Settings(BaseSettings):
    app_name: str = "AI Assistant Backend"
    database_url: str = Field(_DEFAULT_SQLITE_URL)
    secret_key: str = Field("supersecretkey")
    openai_api_key: str = Field("")
    allowed_origins: list[str] = ["*"]
    encryption_key: str = Field("")
    provider_timeout_seconds: int = 15
    provider_retries: int = 2
    provider_fallback: bool = True

    # Official Service Registry (official_service_registry) - source of truth
    # for the /portals catalog. See services/registry_client.py.
    registry_base_url: str = Field("http://127.0.0.1:8004")
    registry_timeout_seconds: float = Field(5.0)

    # Risk Engine (risk_engine) - Phase D Security Shield check called from
    # POST /portals/confirm before a redirect is handed back to the
    # browser. See services/risk_client.py.
    risk_engine_base_url: str = Field("http://127.0.0.1:8005")
    risk_engine_timeout_seconds: float = Field(5.0)

    # Intent Service (intent_service, Phase C1-C4) - text-only intent
    # classification, service resolution, multilingual support, and
    # multi-turn conversation. system_orchestrator is the single
    # integration point between the frontend and intent_service: it never
    # calls this service to make decisions itself, only proxies
    # /conversation/* verbatim. See services/intent_client.py.
    intent_service_base_url: str = Field("http://127.0.0.1:8006")
    intent_service_timeout_seconds: float = Field(5.0)

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"),
        env_file_encoding="utf-8",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_allowed_origins(cls, value):
        # ALLOWED_ORIGINS is documented in .env.example as a comma-separated
        # string (e.g. "*" or "https://a.example,https://b.example").
        # pydantic-settings would otherwise try to JSON-decode a raw env
        # string for a list field and fail on non-JSON values like "*".
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
