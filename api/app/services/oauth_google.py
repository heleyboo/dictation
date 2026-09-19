"""Google OAuth 2.0 authorization-code flow with PKCE (no extra dependency)."""

import base64
import hashlib
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class OAuthError(Exception):
    pass


@dataclass(frozen=True)
class GoogleProfile:
    email: str
    name: str


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def authorization_url(client_id: str, redirect_uri: str, state: str, verifier: str) -> str:
    query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": pkce_challenge(verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{AUTH_URL}?{urlencode(query)}"


class GoogleClient(Protocol):
    async def fetch_profile(self, code: str, verifier: str, redirect_uri: str) -> GoogleProfile: ...


class HttpGoogleClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def fetch_profile(self, code: str, verifier: str, redirect_uri: str) -> GoogleProfile:
        try:
            return await self._fetch_profile(code, verifier, redirect_uri)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise OAuthError(f"Google request failed: {type(exc).__name__}") from exc

    async def _fetch_profile(self, code: str, verifier: str, redirect_uri: str) -> GoogleProfile:
        async with httpx.AsyncClient(timeout=10) as client:
            token_res = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
            if token_res.status_code != 200:
                raise OAuthError(f"token exchange failed ({token_res.status_code})")
            access_token = token_res.json().get("access_token")
            info_res = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            if info_res.status_code != 200:
                raise OAuthError(f"userinfo failed ({info_res.status_code})")
        info = info_res.json()
        if not info.get("email") or not info.get("email_verified"):
            raise OAuthError("Google account has no verified email")
        return GoogleProfile(email=str(info["email"]).lower(), name=str(info.get("name") or ""))
