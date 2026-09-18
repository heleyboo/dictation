"""Current user: profile, settings, account deletion (FR-M1-05)."""

from datetime import time
from decimal import Decimal
from typing import Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator

from app.deps import SESSION_COOKIE, AuthDep, DbDep

router = APIRouter(prefix="/me", tags=["me"])

PLAYBACK_RATES = (0.75, 1.0, 1.25)


class Me(BaseModel):
    id: int
    email: str
    name: str
    role: str
    timezone: str
    email_reminder: bool
    reminder_time: time
    strict_punct_default: bool
    playback_rate_default: float
    csrf_token: str = Field(description="Send back as X-CSRF-Token on state-changing requests")


class MeUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    timezone: str | None = None
    email_reminder: bool | None = None
    reminder_time: time | None = None
    strict_punct_default: bool | None = None
    playback_rate_default: float | None = None

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("unknown IANA timezone")
        return value

    @field_validator("playback_rate_default")
    @classmethod
    def supported_rate(cls, value: float | None) -> float | None:
        if value is not None and value not in PLAYBACK_RATES:
            raise ValueError(f"must be one of {PLAYBACK_RATES}")
        return value


class DeleteAccount(BaseModel):
    confirm_email: str


def _to_me(auth: AuthDep) -> Me:
    u = auth.user
    return Me(
        id=u.id,
        email=u.email,
        name=u.name,
        role=u.role,
        timezone=u.timezone,
        email_reminder=u.email_reminder,
        reminder_time=u.reminder_time,
        strict_punct_default=u.strict_punct_default,
        playback_rate_default=float(u.playback_rate_default),
        csrf_token=auth.session.csrf_token,
    )


@router.get("", response_model=Me)
async def get_me(auth: AuthDep) -> Me:
    return _to_me(auth)


@router.patch("", response_model=Me)
async def update_me(body: MeUpdate, auth: AuthDep, db: DbDep) -> Me:
    changes = body.model_dump(exclude_unset=True)
    if "playback_rate_default" in changes:
        changes["playback_rate_default"] = Decimal(str(changes["playback_rate_default"]))
    for field, value in changes.items():
        if value is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field} cannot be null")
        setattr(auth.user, field, value)
    await db.commit()
    return _to_me(auth)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(body: DeleteAccount, auth: AuthDep, db: DbDep, response: Response) -> None:
    """Deletes the user; sessions (and later progress/vocab) go with it via ON DELETE CASCADE."""
    if body.confirm_email.strip().lower() != auth.user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email xác nhận không khớp")
    await db.delete(auth.user)
    await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
