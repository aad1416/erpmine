import uuid
from datetime import datetime, UTC

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.db.database import Base
from app.support.adapter.credentials import EncryptedString

# Gmail's servers: a Gmail Mailbox needs only its address and app password.
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
IMPLICIT_TLS = "ssl"  # the other TLS mode is "starttls"


class ImapMailbox(Base):
    """One IMAP/SMTP connection per store. The address remains the primary key for
    the Mailbox Registry, and store_id is unique for store-owned settings.

    Host, port and TLS mode default to Gmail's.
    `cursor` is `"<uidvalidity>:<last_uid>"` over INBOX (see `adapter.ImapCursor`),
    owned by the adapter."""

    __tablename__ = "imap_mailboxes"

    mailbox = Column(String, primary_key=True)
    store_id = Column(String, nullable=False, unique=True)
    app_password = Column(EncryptedString, nullable=True)
    imap_host = Column(
        String, nullable=False, default=GMAIL_IMAP_HOST, server_default=GMAIL_IMAP_HOST
    )
    imap_port = Column(
        Integer, nullable=False, default=GMAIL_IMAP_PORT, server_default=str(GMAIL_IMAP_PORT)
    )
    imap_tls_mode = Column(
        String, nullable=False, default=IMPLICIT_TLS, server_default=IMPLICIT_TLS
    )
    smtp_host = Column(
        String, nullable=False, default=GMAIL_SMTP_HOST, server_default=GMAIL_SMTP_HOST
    )
    smtp_port = Column(
        Integer, nullable=False, default=GMAIL_SMTP_PORT, server_default=str(GMAIL_SMTP_PORT)
    )
    smtp_tls_mode = Column(
        String, nullable=False, default=IMPLICIT_TLS, server_default=IMPLICIT_TLS
    )
    cursor = Column(String, nullable=True)


class ImapOutboxStatus:
    captured = "captured"
    delivered = "delivered"


class ImapOutboxMessage(Base):
    """IMAP's own outbox. A message is written here as `captured` in the same
    transaction that moves the Mailbox's cursor past it, and marked `delivered` once the
    sink returns, so a crash in between re-sinks it on the next start. Delivered rows
    are purged after SUPPORT_RETENTION_DAYS; until then they also stop a re-fetched
    message (after a UIDVALIDITY change) from being handed over again."""

    __tablename__ = "imap_outbox"
    __table_args__ = (
        UniqueConstraint("mailbox", "external_message_id", name="uq_imap_outbox_mailbox_message"),
        Index("ix_imap_outbox_mailbox_status", "mailbox", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)  # capture order
    mailbox = Column(String, nullable=False)
    external_message_id = Column(String, nullable=False)
    normalized_payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default=ImapOutboxStatus.captured)
    captured_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    delivered_at = Column(DateTime, nullable=True)


class ImapSentReplyStatus:
    sending = "sending"
    sent = "sent"


class ImapSentReply(Base):
    """One row per reply, keyed by its idempotency key, so a retried reply task doesn't
    email the customer again. Written as `sending` before SMTP and `sent` after; a
    `sending` row left by a crash mid-send is never sent again (see
    `ImapAdapter.send_message`)."""

    __tablename__ = "imap_sent_replies"

    idempotency_key = Column(String, primary_key=True)
    mailbox = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    message_id = Column(String, nullable=True)  # the reply's Message-ID, once built
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    sent_at = Column(DateTime, nullable=True)


class ImapThreadMessage(Base):
    """IMAP-only threading record, one row per message in a Mailbox's Conversations:
    every inbound message captured and every reply we send. Replies read it to set
    In-Reply-To/References and pick the recipient; the fetch path reads it to skip our
    own sent mail. Kept indefinitely — unlike the outbox it is never purged, so a
    Conversation older than SUPPORT_RETENTION_DAYS still threads."""

    __tablename__ = "imap_thread_messages"
    __table_args__ = (
        # NULL message_id (inbound mail without a Message-ID header) is exempt, as NULLs
        # are distinct under SQLite and Postgres.
        UniqueConstraint(
            "adapter", "mailbox", "message_id", name="uq_imap_thread_adapter_mailbox_message_id"
        ),
        Index(
            "ix_imap_thread_adapter_mailbox_conversation", "adapter", "mailbox", "conversation_id"
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    adapter = Column(String, nullable=False)
    mailbox = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    direction = Column(String, nullable=False)  # "inbound" | "outbound"
    message_id = Column(String, nullable=True)  # "<...>", angle brackets kept
    reference_ids = Column(Text, nullable=True)  # this message's References header, space-separated
    sender_address = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    message_at = Column(DateTime, nullable=False)  # INTERNALDATE inbound, send time outbound
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
