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

    # Public origin of the web app (used for OAuth redirect URIs and links in emails).
    app_base_url: str = "http://localhost:8080"
    # Signs short-lived cookies (OAuth state). Must be a long random string in production.
    session_secret: str = "dev-only-insecure-secret"
    session_ttl_days: int = 30
    # Secure cookies need HTTPS; local compose on http://localhost sets this to false.
    cookie_secure: bool = True

    google_client_id: str = ""
    google_client_secret: str = ""

    magic_link_enabled: bool = False
    magic_link_ttl_minutes: int = 15
    magic_link_max_per_hour: int = 5

    # Email: without RESEND_API_KEY the mailer logs messages instead of sending (dev only).
    resend_api_key: str = ""
    email_from: str = "Dictation <no-reply@localhost>"


@lru_cache
def get_settings() -> Settings:
    return Settings()
