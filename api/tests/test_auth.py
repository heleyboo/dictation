from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import func, select, update

from app.deps import SESSION_COOKIE
from app.models import MagicLink, Session, User
from app.routers.auth import OAUTH_COOKIE
from app.services.oauth_google import pkce_challenge
from app.services.tokens import safe_return_to
from tests.support import Harness


async def _count(h: Harness, model: type) -> int:
    async with h.sessions() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/lessons/abc?x=1", "/lessons/abc?x=1"),
        (None, "/"),
        ("", "/"),
        ("https://evil.com", "/"),
        ("//evil.com/x", "/"),
        ("/\\evil.com", "/"),
        ("lessons", "/"),
    ],
)
def test_safe_return_to_blocks_open_redirects(value: str | None, expected: str) -> None:
    assert safe_return_to(value) == expected


async def _google_start(h: Harness, return_to: str = "/lessons/x") -> dict[str, list[str]]:
    res = await h.client.get("/api/v1/auth/google/start", params={"return_to": return_to})
    assert res.status_code == 303
    assert OAUTH_COOKIE in res.cookies
    return parse_qs(urlsplit(res.headers["location"]).query)


async def test_google_sign_in_creates_user_and_session(harness: Harness) -> None:
    query = await _google_start(harness)
    assert query["client_id"] == ["google-client"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://test/api/v1/auth/google/callback"]

    res = await harness.client.get(
        "/api/v1/auth/google/callback", params={"code": "abc", "state": query["state"][0]}
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/lessons/x"
    assert SESSION_COOKIE in res.cookies
    # PKCE: the verifier sent to Google matches the challenge from the start step.
    code, verifier, _ = harness.google.calls[0]
    assert (code, pkce_challenge(verifier)) == ("abc", query["code_challenge"][0])

    me = await harness.client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "learner@example.com"
    assert me.json()["role"] == "learner"


@pytest.mark.parametrize("case", ["wrong_state", "user_cancelled", "google_rejects", "no_state_cookie"])
async def test_google_failures_redirect_to_login_without_creating_user(harness: Harness, case: str) -> None:
    query = await _google_start(harness)
    params = {"code": "abc", "state": query["state"][0]}
    if case == "wrong_state":
        params["state"] = "forged"
    elif case == "user_cancelled":
        params = {"error": "access_denied"}
    elif case == "google_rejects":
        harness.google.profile = None
    elif case == "no_state_cookie":
        harness.client.cookies.clear()

    res = await harness.client.get("/api/v1/auth/google/callback", params=params)
    assert res.status_code == 303
    assert res.headers["location"] == "/login?error=google"
    assert await _count(harness, User) == 0
    assert await _count(harness, Session) == 0


async def test_google_start_404_when_not_configured(sessions) -> None:  # type: ignore[no-untyped-def]
    from tests.support import build_harness, make_settings

    h = build_harness(sessions, make_settings(google_client_id=""))
    async with h.client:
        assert (await h.client.get("/api/v1/auth/google/start")).status_code == 404
        assert (await h.client.get("/api/v1/auth/config")).json() == {
            "google_enabled": False,
            "magic_link_enabled": True,
        }


def _link_token(h: Harness) -> str:
    body = h.mailer.sent[-1].text
    url = next(word for word in body.split() if "magic-link/verify" in word)
    return parse_qs(urlsplit(url).query)["token"][0]


async def test_magic_link_signs_in_once(harness: Harness) -> None:
    res = await harness.client.post(
        "/api/v1/auth/magic-link", json={"email": "New@Example.com", "return_to": "/lessons/y"}
    )
    assert res.status_code == 202
    assert res.json() == {"message": "Kiểm tra email của bạn"}
    assert harness.mailer.sent[-1].to == "new@example.com"
    token = _link_token(harness)

    res = await harness.client.get("/api/v1/auth/magic-link/verify", params={"token": token})
    assert res.status_code == 303 and res.headers["location"] == "/lessons/y"
    assert (await harness.client.get("/api/v1/me")).json()["email"] == "new@example.com"

    harness.client.cookies.clear()
    res = await harness.client.get("/api/v1/auth/magic-link/verify", params={"token": token})
    assert res.headers["location"] == "/login?error=link_expired"


async def test_magic_link_expires(harness: Harness) -> None:
    await harness.client.post("/api/v1/auth/magic-link", json={"email": "a@example.com"})
    token = _link_token(harness)
    async with harness.sessions() as db:
        await db.execute(update(MagicLink).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        await db.commit()
    res = await harness.client.get("/api/v1/auth/magic-link/verify", params={"token": token})
    assert res.headers["location"] == "/login?error=link_expired"
    assert await _count(harness, User) == 0


async def test_magic_link_rate_limited_per_email(harness: Harness) -> None:
    for _ in range(5):
        assert (
            await harness.client.post("/api/v1/auth/magic-link", json={"email": "a@example.com"})
        ).status_code == 202
    assert (
        await harness.client.post("/api/v1/auth/magic-link", json={"email": "a@example.com"})
    ).status_code == 429
    assert (
        await harness.client.post("/api/v1/auth/magic-link", json={"email": "b@example.com"})
    ).status_code == 202


async def test_magic_link_disabled_by_flag(sessions) -> None:  # type: ignore[no-untyped-def]
    from tests.support import build_harness, make_settings

    h = build_harness(sessions, make_settings(magic_link_enabled=False))
    async with h.client:
        assert (
            await h.client.post("/api/v1/auth/magic-link", json={"email": "a@example.com"})
        ).status_code == 404
        assert (
            await h.client.get("/api/v1/auth/magic-link/verify", params={"token": "x"})
        ).status_code == 404
    assert h.mailer.sent == []


async def test_me_requires_login(harness: Harness) -> None:
    assert (await harness.client.get("/api/v1/me")).status_code == 401
    harness.client.cookies.set(SESSION_COOKIE, "not-a-session")
    assert (await harness.client.get("/api/v1/me")).status_code == 401


async def test_expired_session_is_rejected_and_removed(harness: Harness) -> None:
    await harness.login()
    async with harness.sessions() as db:
        await db.execute(update(Session).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        await db.commit()
    assert (await harness.client.get("/api/v1/me")).status_code == 401
    assert await _count(harness, Session) == 0


async def test_session_expiry_slides_with_activity(harness: Harness) -> None:
    await harness.login()
    soon = datetime.now(UTC) + timedelta(days=2)
    async with harness.sessions() as db:
        await db.execute(update(Session).values(expires_at=soon))
        await db.commit()
    assert (await harness.client.get("/api/v1/me")).status_code == 200
    async with harness.sessions() as db:
        expires = (await db.execute(select(Session.expires_at))).scalar_one()
    assert expires > datetime.now(UTC) + timedelta(days=29)


async def test_state_changes_require_csrf_token(harness: Harness) -> None:
    csrf = await harness.login()
    assert (await harness.client.patch("/api/v1/me", json={"name": "X"})).status_code == 403
    assert (
        await harness.client.patch("/api/v1/me", json={"name": "X"}, headers={"X-CSRF-Token": "wrong"})
    ).status_code == 403
    res = await harness.client.patch("/api/v1/me", json={"name": "X"}, headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200 and res.json()["name"] == "X"


async def test_logout_revokes_session(harness: Harness) -> None:
    csrf = await harness.login()
    assert (await harness.client.post("/api/v1/auth/logout")).status_code == 403
    assert (
        await harness.client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    ).status_code == 204
    assert await _count(harness, Session) == 0
    assert (await harness.client.get("/api/v1/me")).status_code == 401


def test_https_deployment_refuses_default_secret() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        Settings(app_base_url="https://dictation.example")
    assert Settings(app_base_url="https://dictation.example", session_secret="x" * 40).cookie_secure
    assert not Settings(app_base_url="http://localhost:8080").cookie_secure
