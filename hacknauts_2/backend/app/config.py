from pathlib import Path
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BASE_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_REPO_ROOT / ".env"),
            str(_BASE_DIR / ".env"),
            ".env",
            "../.env",
        ),
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = "postgresql+psycopg://scalepilot:scalepilot@localhost:5432/scalepilot"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-only-change-me"
    jwt_hours: int = 168
    cors_origins: str = "http://localhost:5173"
    enable_demo: bool = True
    demo_email: str = "demo@scalepilot.ai"
    demo_password: str = "demo1234"

    # Groq API – three agents can use different models; override via env vars.
    groq_api_key: str = ""
    groq_code_model: str = Field(
        default="qwen/qwen3.8-27b",
        validation_alias=AliasChoices("GROQ_CODE_MODEL", "CODE_AGENT_MODEL", "groq_code_model"),
    )
    groq_performance_model: str = Field(
        default="qwen/qwen3.8-27b",
        validation_alias=AliasChoices("GROQ_PERFORMANCE_MODEL", "PERFORMANCE_AGENT_MODEL", "groq_performance_model"),
    )
    groq_optimization_model: str = Field(
        default="qwen/qwen3.8-27b",
        validation_alias=AliasChoices("GROQ_OPTIMIZATION_MODEL", "OPTIMIZATION_AGENT_MODEL", "groq_optimization_model"),
    )
    groq_timeout: int = 60          # seconds per request
    groq_max_retries: int = 5
    groq_temperature: float = 0.2

    # Repository limits
    max_repo_mb: int = 300
    clone_timeout_s: int = 120
    max_files: int = 1500
    max_file_kb: int = 300
    max_findings: int = 60
    ai_max_findings: int = 8        # compact findings sent to Groq to respect 8000 TPM rate limits


settings = Settings()
