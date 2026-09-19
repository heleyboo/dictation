"""Test doubles for external services and helpers to build an authenticated client."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db import get_session
from app.deps import SESSION_COOKIE, get_google_client, get_mailer
from app.main import create_app
from app.models import Role, Session
from app.routers.admin_lessons import get_storage
from app.services.mailer import Email
from app.services.oauth_google import GoogleProfile, OAuthError
from app.services.sessions import create_session
from app.services.users import get_or_create_user


@dataclass
class FakeMailer:
    sent: list[Email] = field(default_factory=list)

    async def send(self, email: Email) -> None:
        self.sent.append(email)


@dataclass
class FakeStorage:
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def get(self, key: str) -> bytes:
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def public_url(self, key: str) -> str:
        return f"http://audio.test/{key}"


@dataclass
class FakeGoogle:
    """Stands in for Google's token + userinfo endpoints."""

    profile: GoogleProfile | None = GoogleProfile(email="learner@example.com", name="Learner")
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    async def fetch_profile(self, code: str, verifier: str, redirect_uri: str) -> GoogleProfile:
        self.calls.append((code, verifier, redirect_uri))
        if self.profile is None:
            raise OAuthError("rejected")
        return self.profile


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_base_url": "http://test",
        "session_secret": "test-secret",
        "google_client_id": "google-client",
        "google_client_secret": "google-secret",
        "magic_link_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@dataclass
class Harness:
    client: httpx.AsyncClient
    sessions: async_sessionmaker[AsyncSession]
    settings: Settings
    mailer: FakeMailer
    google: FakeGoogle
    storage: FakeStorage

    async def login(self, email: str = "learner@example.com", role: str = Role.LEARNER) -> str:
        """Create a user + session directly, set the cookie; returns the CSRF token."""
        async with self.sessions() as db:
            user = await get_or_create_user(db, email)
            user.role = role
            token = await create_session(db, user, timedelta(days=self.settings.session_ttl_days))
            await db.commit()
            csrf = await db.get(Session, _hash(token))
            assert csrf is not None
        self.client.cookies.set(SESSION_COOKIE, token)
        return csrf.csrf_token


def _hash(token: str) -> str:
    from app.services.tokens import hash_token

    return hash_token(token)


def build_harness(sessions: async_sessionmaker[AsyncSession], settings: Settings | None = None) -> Harness:
    settings = settings or make_settings()
    mailer, google, storage = FakeMailer(), FakeGoogle(), FakeStorage()
    app = create_app()

    async def db_override() -> AsyncIterator[AsyncSession]:
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_session] = db_override
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_mailer] = lambda: mailer
    app.dependency_overrides[get_google_client] = lambda: google
    app.dependency_overrides[get_storage] = lambda: storage
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return Harness(client, sessions, settings, mailer, google, storage)


def wav_bytes(seconds: float, rate: int = 8000) -> bytes:
    """Silent mono 8-bit WAV of the given length (valid audio for upload tests)."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(b"\x80" * int(seconds * rate))
    return buf.getvalue()
