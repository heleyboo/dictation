"""Runtime settings, read from environment variables (see repo-root .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://dictation:dictation@localhost:5434/dictation"
    # Worker: seconds between polls when the queue is empty.
    worker_poll_interval: float = 2.0
    # Worker: a running job whose lock is older than this is treated as abandoned and reclaimed.
    worker_lock_timeout: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
