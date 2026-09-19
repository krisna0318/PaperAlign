from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from PAPERALIGN_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PAPERALIGN_",
        extra="ignore",
    )

    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    data_dir: Path = Path(".paperalign")
    log_level: str = "INFO"
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]
    ai_mode: str = "off"
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
