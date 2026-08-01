import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Official Service Registry")
    api_version: str = os.getenv("API_VERSION", "v1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    allowed_origins: list[str] = field(default_factory=lambda: _env_list("ALLOWED_ORIGINS", ["*"]))

    # Path to the canonical service catalog. Defaults to the bundled
    # data/services.json next to this package, but can be pointed at an
    # externally-managed config file (e.g. mounted from a config-map) without
    # any code change.
    services_config_path: str = os.getenv(
        "SERVICES_CONFIG_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "services.json"),
    )


settings = Settings()
