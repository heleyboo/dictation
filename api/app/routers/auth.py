"""Sign-in: Google OAuth (PKCE) and optional email magic link; sign-out."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, EmailStr

from app.config import Settings
from app.deps import SESSION_COOKIE, AuthDep, DbDep, GoogleDep, MailerDep, SettingsDep
from app.models import User
from app.services import magic_links
from app.services.oauth_google import OAuthError, authorization_url
from app.services.sessions import create_session
from app.services.tokens import new_token, safe_return_to
from app.services.users import get_or_create_user

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_COOKIE = "oauth_state"
OAUTH_COOKIE_PATH = "/api/v1/auth/google"
OAUTH_STATE_MAX_AGE = 600


class AuthConfig(BaseModel):
    google_enabled: bool
    magic_link_enabled: bool


class MagicLinkRequest(BaseModel):
    email: EmailStr
    return_to: str = "/"


class MagicLinkAccepted(BaseModel):
    message: str


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="oauth-state")


def _google_redirect_uri(settings: Settings) -> str:
    return f"{settings.app_base_url}/api/v1/auth/google/callback"


async def _sign_in(db: DbDep, settings: Settings, user: User, return_to: str) -> RedirectResponse:
    token = await create_session(db, user, timedelta(days=settings.session_ttl_days))
    await db.commit()
    response = RedirectResponse(safe_return_to(return_to), status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


def _login_error(code: str) -> RedirectResponse:
    return RedirectResponse(f"/login?error={code}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/config", response_model=AuthConfig)
async def auth_config(settings: SettingsDep) -> AuthConfig:
    """Which sign-in methods the login page should show."""
    return AuthConfig(
        google_enabled=bool(settings.google_client_id), magic_link_enabled=settings.magic_link_enabled
    )


@router.get("/google/start", response_class=RedirectResponse, status_code=status.HTTP_303_SEE_OTHER)
async def google_start(settings: SettingsDep, return_to: str = "/") -> RedirectResponse:
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Google sign-in is not configured")
    state, verifier = new_token(), new_token()
    response = RedirectResponse(
        authorization_url(settings.google_client_id, _google_redirect_uri(settings), state, verifier),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        OAUTH_COOKIE,
        _serializer(settings).dumps(
            {"state": state, "verifier": verifier, "return_to": safe_return_to(return_to)}
        ),
        max_age=OAUTH_STATE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=OAUTH_COOKIE_PATH,
    )
    return response


@router.get("/google/callback", response_class=RedirectResponse, status_code=status.HTTP_303_SEE_OTHER)
async def google_callback(
    db: DbDep,
    settings: SettingsDep,
    google: GoogleDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    oauth_state: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    """Any failure (cancelled, bad state, Google error) → /login with an error; no user is created."""
    if error or not code or not state or not oauth_state:
        return _login_error("google")
    try:
        saved = _serializer(settings).loads(oauth_state, max_age=OAUTH_STATE_MAX_AGE)
    except BadSignature:
        return _login_error("google")
    if saved.get("state") != state:
        return _login_error("google")
    try:
        profile = await google.fetch_profile(code, saved["verifier"], _google_redirect_uri(settings))
    except OAuthError:
        return _login_error("google")
    user = await get_or_create_user(db, profile.email, profile.name)
    response = await _sign_in(db, settings, user, saved.get("return_to", "/"))
    response.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
    return response


@router.post("/magic-link", response_model=MagicLinkAccepted, status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(
    body: MagicLinkRequest, db: DbDep, settings: SettingsDep, mailer: MailerDep
) -> MagicLinkAccepted:
    """Same response whether or not the email has an account (no account enumeration, AC-M1-02.1)."""
    if not settings.magic_link_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Magic link sign-in is disabled")
    try:
        await magic_links.request_link(db, mailer, settings, str(body.email), safe_return_to(body.return_to))
    except magic_links.RateLimited:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Bạn đã yêu cầu quá nhiều lần, thử lại sau."
        ) from None
    return MagicLinkAccepted(message="Kiểm tra email của bạn")


@router.get("/magic-link/verify", response_class=RedirectResponse, status_code=status.HTTP_303_SEE_OTHER)
async def verify_magic_link(
    db: DbDep, settings: SettingsDep, token: Annotated[str, Query()]
) -> RedirectResponse:
    if not settings.magic_link_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Magic link sign-in is disabled")
    link = await magic_links.consume_link(db, token)
    if link is None:
        await db.rollback()
        return _login_error("link_expired")
    user = await get_or_create_user(db, link.email)
    return await _sign_in(db, settings, user, link.return_to)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: AuthDep, db: DbDep, response: Response) -> None:
    await db.delete(auth.session)
    await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
