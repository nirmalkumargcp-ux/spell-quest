"""Application settings.

Every tunable number for the adaptive engine lives in `adaptive/config.py`,
not here — this file is infrastructure only.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Adaptive Kids Learning API"
    environment: str = "local"
    debug: bool = True

    # Postgres in docker-compose; SQLite by default so the project runs with no
    # infrastructure at all. Both are exercised by the test suite.
    database_url: str = "sqlite:///./adaptive.db"

    # Deterministic engine: fix this to make question selection reproducible.
    adaptive_seed: int | None = None

    # Media served by the existing static game (photos + Piper audio clips).
    media_base_url: str = "/media"

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
