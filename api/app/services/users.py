from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_or_create_user(db: AsyncSession, email: str, name: str = "") -> User:
    email = email.strip().lower()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(email=email, name=name or email.split("@")[0])
        db.add(user)
        await db.flush()
    elif name and not user.name:
        user.name = name
    return user
