"""Replies over SMTP for an IMAP Mailbox (ADR 0002).

`build_reply` makes a message that threads under its parent in Gmail and in other mail
clients: In-Reply-To the parent, References the parent's References plus the parent,
and the parent's subject with one `Re:`. `SmtpMailboxSender` sends it with aiosmtplib,
logging in with the same app password as IMAP. It never saves a copy to Sent: Gmail
files mail sent through its SMTP server there itself.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from datetime import datetime

import aiosmtplib

from app.support.adapter.imap.accounts import ImapMailboxConfig

_REPLY_PREFIX = re.compile(r"^\s*re\s*:", re.IGNORECASE)


def reply_subject(subject: str | None) -> str:
    subject = (subject or "").strip()
    return subject if _REPLY_PREFIX.match(subject) else f"Re: {subject}".rstrip()


def new_message_id(mailbox_email: str) -> str:
    """A fresh `<...@mailbox-domain>` Message-ID, so we know it before sending."""
    return make_msgid(domain=mailbox_email.rsplit("@", 1)[-1].lower())


def build_reply(
    *,
    from_address: str,
    to_address: str,
    subject: str,
    body_text: str,
    message_id: str,
    in_reply_to: str | None,
    references: list[str],
    sent_at: datetime,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = to_address
    message["Subject"] = subject
    message["Date"] = format_datetime(sent_at)
    message["Message-ID"] = message_id
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = " ".join(references)
    message.set_content(body_text)
    return message


SmtpSend = Callable[..., Awaitable[object]]


class SmtpMailboxSender:
    def __init__(
        self, config: ImapMailboxConfig, timeout: float, smtp_send: SmtpSend = aiosmtplib.send
    ) -> None:
        self._config = config
        self._timeout = timeout
        self._smtp_send = smtp_send

    async def send(self, message: EmailMessage, recipient: str) -> None:
        """Deliver to `recipient` only — the envelope, not the headers, decides who gets
        it. Raises on any SMTP failure (aiosmtplib raises for a refused recipient too)."""
        implicit_tls = self._config.smtp_tls_mode == "ssl"
        await self._smtp_send(
            message,
            sender=self._config.email,
            recipients=[recipient],
            hostname=self._config.smtp_host,
            port=self._config.smtp_port,
            username=self._config.email,
            password=self._config.app_password,
            use_tls=implicit_tls,
            start_tls=not implicit_tls,
            timeout=self._timeout,
        )
