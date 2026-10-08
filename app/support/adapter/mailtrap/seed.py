"""Copies the env-configured Mailtrap inboxes (`MAILTRAP_*_1` / `_2`) into
`mailtrap_mailboxes`. Leaves the cursor alone, which the adapter owns.

Only the seed script reads these variables; the app reads the table.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.mailtrap.models import MailtrapMailbox
from app.support.adapter.seeding import seeder


class MailtrapSeedSettings(BaseSettings):
    """Each inbox needs its own names; one whose address is unset is skipped. No
    defaults: an inbox's API token is a secret."""

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    MAILTRAP_INBOX_ADDRESS_1: str | None = None
    MAILTRAP_INBOX_ID_1: str | None = None
    MAILTRAP_API_TOKEN_1: str | None = None

    MAILTRAP_INBOX_ADDRESS_2: str | None = None
    MAILTRAP_INBOX_ID_2: str | None = None
    MAILTRAP_API_TOKEN_2: str | None = None


@seeder("mailtrap")
def seed_mailtrap_mailboxes() -> list[MailtrapMailbox]:
    seed_settings = MailtrapSeedSettings()
    rows = []
    for inbox_number in (1, 2):
        address = getattr(seed_settings, f"MAILTRAP_INBOX_ADDRESS_{inbox_number}")
        if not address:
            continue
        rows.append(
            MailtrapMailbox(
                mailbox=MailboxKey.of("mailtrap", address).mailbox,
                inbox_id=getattr(seed_settings, f"MAILTRAP_INBOX_ID_{inbox_number}"),
                api_token=getattr(seed_settings, f"MAILTRAP_API_TOKEN_{inbox_number}"),
            )
        )
    return rows
