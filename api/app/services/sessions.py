"""Server-side sessions: create, resolve from cookie token (sliding expiry), revoke."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, User
from app.services.tokens import hash_token, new_token

# Extend a session at most once per day to avoid a write on every request.
_REFRESH_AFTER = timedelta(days=1)


async def create_session(db: AsyncSession, user: User, ttl: timedelta) -> str:
    """Returns the raw cookie token; only its hash is stored."""
    token = new_token()
    db.add(
        Session(
            token_hash=hash_token(token),
            user_id=user.id,
            csrf_token=new_token(),
            expires_at=datetime.now(UTC) + ttl,
        )
    )
    await db.flush()
    return token


async def resolve_session(db: AsyncSession, token: str, ttl: timedelta) -> tuple[Session, User] | None:
    row = (
        await db.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(Session.token_hash == hash_token(token))
        )
    ).one_or_none()
    if row is None:
        return None
    session, user = row
    now = datetime.now(UTC)
    if session.expires_at <= now:
        await db.delete(session)
        await db.commit()
        return None
    # Sliding expiry: 30 days of inactivity (SRS AC-M1-03.1).
    if session.expires_at - ttl + _REFRESH_AFTER <= now:
        session.expires_at = now + ttl
        await db.commit()
    return session, user


async def revoke_session(db: AsyncSession, token: str) -> None:
    await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
    await db.commit()
