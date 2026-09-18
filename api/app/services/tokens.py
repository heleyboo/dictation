"""Random tokens and safe redirect targets."""

import hashlib
import secrets
from urllib.parse import urlsplit


def new_token() -> str:
    """URL-safe random token (256 bits)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored hashed so a database leak does not expose live sessions or login links."""
    return hashlib.sha256(token.encode()).hexdigest()


def safe_return_to(value: str | None) -> str:
    """Only allow same-site absolute paths (prevents open redirects such as `//evil.com` or `https://…`)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return "/"
    return value
