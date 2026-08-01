import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Input Validation & Security Engine")
    api_version: str = os.getenv("API_VERSION", "v1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    allowed_origins: list[str] = field(
        default_factory=lambda: _env_list("ALLOWED_ORIGINS", ["*"])
    )

    # Metadata validation limits
    max_file_size_bytes: int = _env_int("MAX_FILE_SIZE_BYTES", 5 * 1024 * 1024)  # 5 MB
    max_page_count: int = _env_int("MAX_PAGE_COUNT", 10)
    allowed_mime_types: list[str] = field(
        default_factory=lambda: _env_list(
            "ALLOWED_MIME_TYPES",
            ["application/pdf", "image/jpeg", "image/jpg", "image/png"],
        )
    )

    # OCR input validation limits
    min_ocr_text_length: int = _env_int("MIN_OCR_TEXT_LENGTH", 10)
    max_ocr_text_length: int = _env_int("MAX_OCR_TEXT_LENGTH", 20000)
    min_alnum_ratio_percent: int = _env_int("MIN_ALNUM_RATIO_PERCENT", 30)

    # Official Service Registry (official_service_registry) - source of truth
    # for which documents a service requires and its eligibility rules.
    # See services/registry_client.py.
    registry_base_url: str = os.getenv("REGISTRY_BASE_URL", "http://127.0.0.1:8004")
    registry_timeout_seconds: float = float(os.getenv("REGISTRY_TIMEOUT_SECONDS", "5"))


settings = Settings()
