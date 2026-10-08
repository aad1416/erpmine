"""Gmail API adapter settings, read from `SUPPORT_GMAIL_*` environment variables.

The Gmail Mailboxes themselves (address, refresh token, history cursor) live in the
`gmail_mailboxes` table, not here. The OAuth client is one app for every Mailbox, so its
ID and secret are app-wide and stay in the environment, with no defaults in code.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class GmailSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPPORT_GMAIL_",
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    CLIENT_ID: str | None = None
    CLIENT_SECRET: str | None = None

    # "poll": each Mailbox is read every POLL_INTERVAL_SECONDS. "push": Gmail notifies the
    # Pub/Sub webhook of new mail, and each Mailbox is also read every
    # BACKUP_POLL_INTERVAL_SECONDS in case a notification was dropped.
    DETECTION_MODE: Literal["poll", "push"] = "poll"
    POLL_INTERVAL_SECONDS: float = 60
    # Every 15 minutes, as often as Gmail was re-read in push mode before this adapter
    # read its own Mailboxes.
    BACKUP_POLL_INTERVAL_SECONDS: float = 15 * 60

    # Push mode: the topic each Mailbox's users.watch() publishes to, and the audience
    # the webhook checks Pub/Sub's token against (unset: the token isn't checked).
    PUBSUB_TOPIC: str | None = None
    PUBSUB_AUDIENCE: str | None = None
    # A watch expires after 7 days; renewing daily leaves plenty of room for failures.
    WATCH_RENEWAL_INTERVAL_SECONDS: float = 24 * 60 * 60

    # Bounds each Gmail API request. A request that hangs raises, and the Mailbox's next
    # read retries it.
    TIMEOUT_SECONDS: float = 30

    @field_validator("DETECTION_MODE", mode="before")
    @classmethod
    def _normalize_detection_mode(cls, value: object) -> object:
        if value is None:
            return "poll"
        return value.strip().lower() if isinstance(value, str) else value


gmail_settings = GmailSettings()
