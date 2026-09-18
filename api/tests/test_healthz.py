from collections.abc import AsyncIterator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import create_app


async def _client(sessions: async_sessionmaker[AsyncSession]) -> httpx.AsyncClient:
    app = create_app()

    async def override() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_healthz_ok(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with await _client(sessions) as client:
        res = await client.get("/api/v1/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": "ok"}


async def test_healthz_reports_unreachable_database() -> None:
    dead = create_async_engine("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none")
    try:
        async with await _client(async_sessionmaker(dead)) as client:
            res = await client.get("/api/v1/healthz")
    finally:
        await dead.dispose()
    assert res.status_code == 503
    assert res.json() == {"status": "degraded", "db": "unreachable"}
