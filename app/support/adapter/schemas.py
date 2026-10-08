"""Wire-format contract shared by every adapter (02-architecture-decisions.md §12.1)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.support.adapter.mailbox_key import MailboxKey


class NormalizedMessage(BaseModel):
    """The channel-agnostic message shape every adapter must produce. `adapter` +
    `mailbox` identify the Mailbox it came in to."""

    adapter: str
    mailbox: str
    conversation_id: str
    external_message_id: str
    sender_address: str
    sender_name: str | None = None
    received_at: datetime
    body_text: str
    subject: str | None = None
    has_attachments: bool = False

    @field_validator("mailbox")
    @classmethod
    def _lower_case_mailbox(cls, mailbox: str) -> str:
        """Mailbox addresses are stored lower-cased (MailboxKey.of)."""
        return mailbox.lower()

    @property
    def mailbox_key(self) -> MailboxKey:
        return MailboxKey(self.adapter, self.mailbox)
