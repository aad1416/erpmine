"""Mailtrap adapter settings, read from `SUPPORT_MAILTRAP_*` environment variables.

The Mailtrap Mailboxes themselves (inbox address, inbox ID, API token) live in the
`mailtrap_mailboxes` table, not here.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class MailtrapSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPORT_MAILTRAP_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Short, since a dev loop is useless if a developer waits to see a test email arrive.
    POLL_INTERVAL_SECONDS: float = 15
    # Push isn't built: "push" makes the adapter refuse to start rather than silently
    # never read mail.
    DETECTION_MODE: Literal["poll", "push"] = "poll"


mailtrap_settings = MailtrapSettings()
