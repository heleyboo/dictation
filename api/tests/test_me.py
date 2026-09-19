import pytest
from fastapi import APIRouter, FastAPI
from sqlalchemy import func, select

from app.deps import AdminDep
from app.models import Role, Session, User
from tests.support import Harness


async def test_me_returns_settings_and_csrf(harness: Harness) -> None:
    csrf = await harness.login()
    body = (await harness.client.get("/api/v1/me")).json()
    assert body["csrf_token"] == csrf
    assert body["timezone"] == "Asia/Saigon"
    assert body["reminder_time"] == "20:00:00"
    assert body["playback_rate_default"] == 1.0
    assert body["strict_punct_default"] is False


async def test_update_settings(harness: Harness) -> None:
    csrf = await harness.login()
    res = await harness.client.patch(
        "/api/v1/me",
        json={
            "timezone": "Europe/Berlin",
            "email_reminder": True,
            "reminder_time": "07:30",
            "strict_punct_default": True,
            "playback_rate_default": 0.75,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    body = res.json()
    assert (body["timezone"], body["reminder_time"], body["playback_rate_default"]) == (
        "Europe/Berlin",
        "07:30:00",
        0.75,
    )
    assert body["email_reminder"] is True and body["strict_punct_default"] is True


@pytest.mark.parametrize(
    "payload",
    [{"timezone": "Mars/Base"}, {"playback_rate_default": 2}, {"name": ""}, {"email_reminder": None}],
)
async def test_invalid_settings_rejected(harness: Harness, payload: dict[str, object]) -> None:
    csrf = await harness.login()
    res = await harness.client.patch("/api/v1/me", json=payload, headers={"X-CSRF-Token": csrf})
    assert res.status_code == 422


async def test_delete_account_requires_matching_email(harness: Harness) -> None:
    csrf = await harness.login("del@example.com")
    headers = {"X-CSRF-Token": csrf}
    res = await harness.client.request(
        "DELETE", "/api/v1/me", json={"confirm_email": "x@y.z"}, headers=headers
    )
    assert res.status_code == 400
    res = await harness.client.request(
        "DELETE", "/api/v1/me", json={"confirm_email": " DEL@example.com "}, headers=headers
    )
    assert res.status_code == 204
    async with harness.sessions() as db:
        assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 0
        assert (await db.execute(select(func.count()).select_from(Session))).scalar_one() == 0


async def test_admin_guard(harness: Harness) -> None:
    probe = APIRouter()

    @probe.get("/api/v1/admin/probe")
    async def admin_probe(auth: AdminDep) -> dict[str, str]:
        return {"email": auth.user.email}

    app = harness.client._transport.app  # type: ignore[attr-defined]
    assert isinstance(app, FastAPI)
    app.include_router(probe)

    assert (await harness.client.get("/api/v1/admin/probe")).status_code == 401
    await harness.login("learner@example.com", Role.LEARNER)
    assert (await harness.client.get("/api/v1/admin/probe")).status_code == 403
    await harness.login("boss@example.com", Role.ADMIN)
    assert (await harness.client.get("/api/v1/admin/probe")).json() == {"email": "boss@example.com"}
