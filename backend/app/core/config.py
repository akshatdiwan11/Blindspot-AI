"""Application settings, read from environment variables (see .env.example).

Secrets such as LLM API keys are only ever read from the environment. They are
never stored in the database and never returned by the API.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Blindspot AI"
    environment: str = "development"
    log_level: str = "INFO"

    # Database. PostgreSQL in Docker/production; SQLite works for quick local runs and tests.
    database_url: str = "postgresql+psycopg2://blindspot:blindspot@localhost:5432/blindspot"

    # CORS origins for the frontend (comma separated).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Upload limits.
    max_upload_mb: float = 10.0
    max_rows: int = 20000
    storage_dir: Path = BACKEND_DIR / "storage"

    # Data retention: projects older than this many days are deleted on startup. 0 disables.
    retention_days: int = 0

    # Failure discovery defaults.
    min_group_size: int = 20
    fdr_alpha: float = 0.05

    # LLM provider configuration. Nothing is sent to an LLM unless the project enables it.
    llm_provider: str = "openai"  # "openai" or "openai_compatible"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = Field(default=None, repr=False)
    llm_api_key: str | None = Field(default=None, repr=False)  # for openai_compatible providers
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 3000
    # Price per 1M tokens (input, output) used for cost tracking. Override for your model.
    llm_input_price_per_m: float = 0.15
    llm_output_price_per_m: float = 0.60
    # Hard cap on estimated LLM spend per UTC day across the whole deployment. 0 disables the cap.
    llm_daily_budget_usd: float = 2.0

    # Optional sentence-transformer model for embeddings (only used if installed and enabled).
    enable_embeddings: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Render and Heroku hand out postgres:// URLs; SQLAlchemy needs the dialect spelled out.
        if v.startswith("postgres://"):
            v = "postgresql+psycopg2://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+psycopg2://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def active_api_key(self) -> str | None:
        if self.llm_provider == "openai":
            return self.openai_api_key or self.llm_api_key
        return self.llm_api_key or self.openai_api_key

    @property
    def llm_configured(self) -> bool:
        return bool(self.active_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
