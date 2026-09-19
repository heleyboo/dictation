"""Shared FastAPI dependencies: settings, DB session, auth, CSRF, external clients."""

import hmac
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Role, Session, User
from app.services.mailer import Mailer, build_mailer
from app.services.oauth_google import GoogleClient, HttpGoogleClient
from app.services.sessions import resolve_session

SESSION_COOKIE = "sid"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncSession, Depends(get_session)]


def get_mailer(settings: SettingsDep) -> Mailer:
    return build_mailer(settings)


def get_google_client(settings: SettingsDep) -> GoogleClient:
    return HttpGoogleClient(settings.google_client_id, settings.google_client_secret)


MailerDep = Annotated[Mailer, Depends(get_mailer)]
GoogleDep = Annotated[GoogleClient, Depends(get_google_client)]


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@dataclass(frozen=True)
class Auth:
    user: User
    session: Session


async def get_optional_auth(
    db: DbDep,
    settings: SettingsDep,
    response: Response,
    sid: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Auth | None:
    if not sid:
        return None
    resolved = await resolve_session(db, sid, timedelta(days=settings.session_ttl_days))
    if resolved is None:
        return None
    session, user, extended = resolved
    if extended:
        # Keep the browser cookie alive as long as the server-side session (AC-M1-03.1).
        set_session_cookie(response, sid, settings)
    return Auth(user=user, session=session)


async def require_auth(
    request: Request,
    auth: Annotated[Auth | None, Depends(get_optional_auth)],
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> Auth:
    """Logged-in user; state-changing requests must echo the session's CSRF token (AC-M1-03.2)."""
    if auth is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    if request.method not in SAFE_METHODS and not hmac.compare_digest(
        (x_csrf_token or "").encode(), auth.session.csrf_token.encode()
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token không hợp lệ")
    return auth


async def require_admin(auth: Annotated[Auth, Depends(require_auth)]) -> Auth:
    if auth.user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cần quyền admin")
    return auth


AuthDep = Annotated[Auth, Depends(require_auth)]
AdminDep = Annotated[Auth, Depends(require_admin)]
