from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

NAME_MAX = 120


async def get_or_create_user(db: AsyncSession, email: str, name: str = "") -> User:
    """Idempotent under concurrent first sign-ins (ON CONFLICT DO NOTHING, then read back)."""
    email = email.strip().lower()
    name = name.strip()[:NAME_MAX]
    await db.execute(
        insert(User)
        .values(email=email, name=name or email.split("@")[0][:NAME_MAX])
        .on_conflict_do_nothing(index_elements=[User.email])
    )
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    if name and not user.name:
        user.name = name
    return user
