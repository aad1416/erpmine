"""Copies the env-configured Gmail API Mailbox into `gmail_mailboxes`. Leaves the history
cursor alone, which the adapter owns, and a stored refresh token alone when the env has
none.

Only the seed script reads these variables; the app reads the table.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.support.adapter.gmail.models import GmailMailbox
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.seeding import seeder


class GmailSeedSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    GMAIL_USER_EMAIL: str | None = None
    GMAIL_REFRESH_TOKEN: str | None = None


@seeder("gmail")
def seed_gmail_mailboxes() -> list[GmailMailbox]:
    seed_settings = GmailSeedSettings()
    if not seed_settings.GMAIL_USER_EMAIL:
        return []
    row = GmailMailbox(mailbox=MailboxKey.of("gmail", seed_settings.GMAIL_USER_EMAIL).mailbox)
    if seed_settings.GMAIL_REFRESH_TOKEN:
        row.refresh_token = seed_settings.GMAIL_REFRESH_TOKEN
    return [row]
