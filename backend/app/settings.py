from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.enums import AiMode


class Settings(BaseSettings):
    """Runtime settings loaded from PAPERALIGN_* environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PAPERALIGN_",
        env_ignore_empty=True,
        hide_input_in_errors=True,
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
    ai_mode: AiMode = AiMode.OFF
    ai_provider: Literal["openai_responses", "deepseek_responses"] = "deepseek_responses"
    ai_base_url: str | None = None
    ai_api_key: SecretStr | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = Field(default=30, gt=0, le=120)
    ai_max_output_tokens: int = Field(default=500, ge=100, le=2000)
    ai_max_retries: int = Field(default=1, ge=0, le=3)
    ai_input_cost_per_million: float | None = Field(default=None, ge=0)
    ai_output_cost_per_million: float | None = Field(default=None, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
