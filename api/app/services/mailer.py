"""Outgoing email. Resend in production; without an API key messages are logged (local dev)."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings

log = logging.getLogger("mailer")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str | None = None


class Mailer(Protocol):
    async def send(self, email: Email) -> None: ...


class LogMailer:
    async def send(self, email: Email) -> None:
        log.warning(
            "email not sent (RESEND_API_KEY unset) to=%s subject=%s\n%s", email.to, email.subject, email.text
        )


class ResendMailer:
    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    async def send(self, email: Email) -> None:
        payload: dict[str, object] = {
            "from": self._sender,
            "to": [email.to],
            "subject": email.subject,
            "text": email.text,
        }
        if email.html:
            payload["html"] = email.html
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            res.raise_for_status()


def build_mailer(settings: Settings) -> Mailer:
    if settings.resend_api_key:
        return ResendMailer(settings.resend_api_key, settings.email_from)
    return LogMailer()
