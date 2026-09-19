"""Runtime settings, read from environment variables (see repo-root .env.example)."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SESSION_SECRET = "dev-only-insecure-secret"


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
    session_secret: str = DEV_SESSION_SECRET
    session_ttl_days: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""

    magic_link_enabled: bool = False
    magic_link_ttl_minutes: int = 15
    magic_link_max_per_hour: int = 5

    # Email: without RESEND_API_KEY the mailer logs messages instead of sending (dev only).
    resend_api_key: str = ""
    email_from: str = "Dictation <no-reply@localhost>"

    # Audio storage (S3-compatible: Cloudflare R2 in production, minio locally).
    s3_endpoint_url: str = "http://localhost:9010"
    s3_bucket: str = "dictation-audio"
    s3_access_key_id: str = "dictation"
    s3_secret_access_key: str = "dictation-dev-secret"
    s3_region: str = "auto"
    # Browser-facing base URL for audio objects (bucket must allow public reads + HTTP Range).
    s3_public_base_url: str = "http://localhost:9010/dictation-audio"

    # LLMs. The SDK reads ANTHROPIC_API_KEY itself.
    # Word lookup (phase 4): frequent, latency-sensitive → Haiku.
    llm_model: str = "claude-haiku-4-5"
    # Sentence translation at ingest: once per lesson, quality matters. Measured on a real VOA lesson:
    # Haiku mistranslated idioms/names ("spend the winter", "milkweed"); Sonnet 5 did not (≈$0.03/lesson).
    translate_model: str = "claude-sonnet-5"
    # Forced alignment model (stable-ts / Whisper); worker only.
    align_model: str = "base.en"

    # Upload limits (AC-M2-01.2, AC-M2-01.3).
    max_audio_bytes: int = 30 * 1024 * 1024
    max_audio_seconds: int = 15 * 60
    max_transcript_chars: int = 20_000

    @property
    def cookie_secure(self) -> bool:
        """Cookies are Secure whenever the app is served over HTTPS (i.e. anything but local dev)."""
        return self.app_base_url.startswith("https://")

    @model_validator(mode="after")
    def _https_needs_real_secret(self) -> "Settings":
        if self.cookie_secure and self.session_secret == DEV_SESSION_SECRET:
            raise ValueError("SESSION_SECRET must be set when APP_BASE_URL is https")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
