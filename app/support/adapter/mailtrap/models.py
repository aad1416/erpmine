from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, String

from app.db.database import Base
from app.support.adapter.credentials import EncryptedString


class MailtrapMailbox(Base):
    """Mailtrap's Mailbox Connection table: one row per Mailtrap inbox, keyed by the
    inbox address alone (the Mailbox Registry reads the primary key).

    `api_token` and `inbox_id` are nullable only because the migration that moved the
    cursor here creates a row per Mailbox before the seeder fills in its credentials;
    the adapter doesn't poll a Mailbox missing either. `cursor` is the `received_at` of
    the last message handed to the sink, owned by the adapter."""

    __tablename__ = "mailtrap_mailboxes"

    mailbox = Column(String, primary_key=True)
    inbox_id = Column(String, nullable=True)
    api_token = Column(EncryptedString, nullable=True)
    cursor = Column(String, nullable=True)


class MailtrapLastInboundMessage(Base):
    """The newest inbound message of each Conversation: Mailtrap replies to a message,
    not to a thread, so a reply targets this one."""

    __tablename__ = "mailtrap_last_inbound_messages"

    mailbox = Column(String, primary_key=True)
    conversation_id = Column(String, primary_key=True)
    external_message_id = Column(String, nullable=False)
    received_at = Column(String, nullable=False)  # Mailtrap's ISO 8601 timestamp, as the cursor


class MailtrapSentReply(Base):
    """One row per reply sent, keyed by its idempotency key, so a retried reply task
    doesn't email the customer again."""

    __tablename__ = "mailtrap_sent_replies"

    idempotency_key = Column(String, primary_key=True)
    mailbox = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    sent_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
