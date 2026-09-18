"""Passwordless email sign-in: single-use, short-lived, rate-limited links (FR-M1-02)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import MagicLink
from app.services.mailer import Email, Mailer
from app.services.tokens import hash_token, new_token


class RateLimited(Exception):
    pass


async def request_link(
    db: AsyncSession, mailer: Mailer, settings: Settings, email: str, return_to: str
) -> None:
    email = email.strip().lower()
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent = (
        await db.execute(
            select(func.count())
            .select_from(MagicLink)
            .where(MagicLink.email == email, MagicLink.created_at > hour_ago)
        )
    ).scalar_one()
    if recent >= settings.magic_link_max_per_hour:
        raise RateLimited
    token = new_token()
    db.add(
        MagicLink(
            email=email,
            token_hash=hash_token(token),
            return_to=return_to,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes),
        )
    )
    await db.commit()
    link = f"{settings.app_base_url}/api/v1/auth/magic-link/verify?token={token}"
    await mailer.send(
        Email(
            to=email,
            subject="Đăng nhập Dictation",
            text=(
                f"Bấm vào liên kết sau để đăng nhập (hết hạn sau {settings.magic_link_ttl_minutes} phút, "
                f"chỉ dùng được một lần):\n\n{link}\n\nNếu bạn không yêu cầu, hãy bỏ qua email này."
            ),
        )
    )


async def consume_link(db: AsyncSession, token: str) -> MagicLink | None:
    """Atomically mark the link used; returns None if unknown, expired or already used."""
    now = datetime.now(UTC)
    link = (
        await db.execute(
            update(MagicLink)
            .where(
                MagicLink.token_hash == hash_token(token),
                MagicLink.used_at.is_(None),
                MagicLink.expires_at > now,
            )
            .values(used_at=now)
            .returning(MagicLink)
        )
    ).scalar_one_or_none()
    return link
