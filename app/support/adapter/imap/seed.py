"""Copies the env-configured IMAP Mailbox into `imap_mailboxes`. Sets every column but the
cursor, which the adapter owns, so a host setting removed from the env goes back to
Gmail's.

Only the seed script reads these variables; the app reads the table.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.support.adapter.imap.models import (
    GMAIL_IMAP_HOST,
    GMAIL_IMAP_PORT,
    GMAIL_SMTP_HOST,
    GMAIL_SMTP_PORT,
    IMPLICIT_TLS,
    ImapMailbox,
)
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.seeding import seeder


class ImapSeedSettings(BaseSettings):
    """A Mailbox connected with an app password (ADR 0002). Host, port and TLS mode
    ("ssl" or "starttls") default to Gmail's when unset."""

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    IMAP_MAILBOX_EMAIL: str | None = None
    IMAP_MAILBOX_STORE_ID: str | None = None
    IMAP_MAILBOX_APP_PASSWORD: str | None = None
    IMAP_HOST: str | None = None
    IMAP_PORT: int | None = None
    IMAP_TLS_MODE: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = None
    SMTP_TLS_MODE: str | None = None


@seeder("imap")
def seed_imap_mailboxes() -> list[ImapMailbox]:
    seed_settings = ImapSeedSettings()
    if not seed_settings.IMAP_MAILBOX_EMAIL:
        return []
    if not seed_settings.IMAP_MAILBOX_STORE_ID or not seed_settings.IMAP_MAILBOX_STORE_ID.strip():
        raise ValueError("IMAP_MAILBOX_STORE_ID is required when seeding an IMAP mailbox")
    return [
        ImapMailbox(
            mailbox=MailboxKey.of("imap", seed_settings.IMAP_MAILBOX_EMAIL).mailbox,
            store_id=seed_settings.IMAP_MAILBOX_STORE_ID.strip(),
            app_password=seed_settings.IMAP_MAILBOX_APP_PASSWORD,
            imap_host=seed_settings.IMAP_HOST or GMAIL_IMAP_HOST,
            imap_port=seed_settings.IMAP_PORT or GMAIL_IMAP_PORT,
            imap_tls_mode=seed_settings.IMAP_TLS_MODE or IMPLICIT_TLS,
            smtp_host=seed_settings.SMTP_HOST or GMAIL_SMTP_HOST,
            smtp_port=seed_settings.SMTP_PORT or GMAIL_SMTP_PORT,
            smtp_tls_mode=seed_settings.SMTP_TLS_MODE or IMPLICIT_TLS,
        )
    ]
