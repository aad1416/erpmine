"""IMAP/SMTP adapter settings, read from `SUPPORT_IMAP_*` environment variables.

The IMAP Mailboxes themselves (address, app password, servers) live in the
`imap_mailboxes` table, not here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ImapSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPORT_IMAP_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    POLL_INTERVAL_SECONDS: float = 60
    # Bounds every IMAP step (connect and each command) and each SMTP send. A step that
    # hangs raises, and the next poll reconnects.
    TIMEOUT_SECONDS: float = 30


imap_settings = ImapSettings()
