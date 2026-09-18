from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.routers import admin_lessons, auth, me


class Health(BaseModel):
    status: str
    db: str


api = APIRouter(prefix="/api/v1")


@api.get(
    "/healthz",
    response_model=Health,
    responses={503: {"model": Health, "description": "Database unreachable"}},
    tags=["system"],
)
async def healthz(response: Response, session: Annotated[AsyncSession, Depends(get_session)]) -> Health:
    """Liveness + database reachability. Returns 503 when Postgres is unreachable."""
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Health(status="degraded", db="unreachable")
    return Health(status="ok", db="ok")


api.include_router(auth.router)
api.include_router(me.router)
api.include_router(admin_lessons.router)


def create_app() -> FastAPI:
    app = FastAPI(title="Dictation API", version="0.1.0")
    app.include_router(api)
    return app


app = create_app()
