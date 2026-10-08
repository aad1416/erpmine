from datetime import datetime, UTC

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.db.database import Base
from app.support.adapter.credentials import EncryptedString


class GmailMailbox(Base):
    """The Gmail API's Mailbox Connection table: one row per Mailbox, keyed by its
    address alone (the Mailbox Registry reads the primary key).

    `refresh_token` is the Mailbox's own OAuth grant; the OAuth client it was issued to
    is app-wide (`SUPPORT_GMAIL_CLIENT_ID` / `_SECRET`). It is nullable only because the
    migration that moved the cursor here creates a row per Mailbox before the seeder
    fills it in; the adapter doesn't serve a Mailbox without one. `history_id` is the
    cursor: the Gmail historyId the Mailbox has been read up to, owned by the adapter."""

    __tablename__ = "gmail_mailboxes"

    mailbox = Column(String, primary_key=True)
    refresh_token = Column(EncryptedString, nullable=True)
    history_id = Column(String, nullable=True)


class GmailOutboxStatus:
    captured = "captured"
    delivered = "delivered"


class GmailOutboxMessage(Base):
    """The Gmail API adapter's own outbox. A message is written here as `captured` in
    the same transaction that moves the Mailbox's history cursor past it, and marked
    `delivered` once the sink returns, so a crash in between re-sinks it on the next
    start. Delivered rows are purged after SUPPORT_RETENTION_DAYS; until then they also
    stop a re-read message from being handed over again."""

    __tablename__ = "gmail_outbox"
    __table_args__ = (
        UniqueConstraint(
            "mailbox", "external_message_id", name="uq_gmail_outbox_mailbox_message"
        ),
        Index("ix_gmail_outbox_mailbox_status", "mailbox", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)  # capture order
    mailbox = Column(String, nullable=False)
    external_message_id = Column(String, nullable=False)
    normalized_payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default=GmailOutboxStatus.captured)
    captured_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    delivered_at = Column(DateTime, nullable=True)


class GmailSentReplyStatus:
    sending = "sending"
    sent = "sent"


class GmailSentReply(Base):
    """One row per reply, keyed by its idempotency key, so a retried reply task doesn't
    email the customer again. Written as `sending` before the Gmail API call and `sent`
    after; a `sending` row left by a crash mid-send is resolved by looking for the reply
    in its thread (see `GmailAdapter.send_message`)."""

    __tablename__ = "gmail_sent_replies"

    idempotency_key = Column(String, primary_key=True)
    mailbox = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    sent_at = Column(DateTime, nullable=True)


class GmailWatch(Base):
    """Each push-mode Mailbox's users.watch() registration: the historyId and expiry
    Gmail returned when it was last renewed."""

    __tablename__ = "gmail_watches"

    adapter = Column(String, primary_key=True)
    mailbox = Column(String, primary_key=True)
    history_id = Column(String, nullable=True)
    watch_expiration = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
