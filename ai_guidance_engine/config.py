import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI Guidance Engine")
    api_version: str = os.getenv("API_VERSION", "v1")

    # Gemini
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    gemini_base_url: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")

    # OpenAI
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # Claude (Anthropic)
    claude_api_key: str | None = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    claude_base_url: str = os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com/v1")
    claude_api_version: str = os.getenv("CLAUDE_API_VERSION", "2023-06-01")

    # Azure OpenAI
    azure_openai_api_key: str | None = os.getenv("AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str | None = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    # Ollama (local, no API key required)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")

    allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    )

    # Risk Engine (Phase D Security Shield) - used to content-scan
    # AI-generated extraction output (field values/reasons) for sensitive-field
    # indicators (OTP/password/PIN/CVV) before it's returned to any caller,
    # the same way system_orchestrator scans redirects before they happen.
    risk_engine_base_url: str = os.getenv("RISK_ENGINE_BASE_URL", "http://127.0.0.1:8005")
    risk_engine_timeout_seconds: float = float(os.getenv("RISK_ENGINE_TIMEOUT_SECONDS", "3"))
    content_scan_enabled: bool = os.getenv("CONTENT_SCAN_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

    provider_name: str = os.getenv("DEFAULT_PROVIDER", "gemini")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_backoff_base_seconds: float = float(os.getenv("RETRY_BACKOFF_BASE_SECONDS", "0.5"))
    retry_backoff_max_seconds: float = float(os.getenv("RETRY_BACKOFF_MAX_SECONDS", "8"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
