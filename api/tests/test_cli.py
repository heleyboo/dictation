import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app import cli
from app.models import Role, User


async def test_make_admin_creates_or_promotes_user(
    monkeypatch: pytest.MonkeyPatch, engine: AsyncEngine, sessions: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(cli, "session_factory", lambda: sessions)
    monkeypatch.setattr(cli, "get_engine", lambda: engine)
    await cli.make_admin("Boss@Example.com")
    async with sessions() as db:
        user = (await db.execute(select(User))).scalar_one()
    assert (user.email, user.role) == ("boss@example.com", Role.ADMIN)
