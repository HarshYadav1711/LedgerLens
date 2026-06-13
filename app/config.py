from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    app_name: str = "LedgerLens"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql://ledgerlens:ledgerlens@localhost:5432/ledgerlens"

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"

    # Ollama (local LLM — no paid APIs)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Processing
    upload_dir: str = "/app/uploads"
    llm_batch_size: int = 25
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
