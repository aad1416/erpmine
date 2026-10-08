"""Reads and writes `imap_thread_messages` (see `models.ImapThreadMessage`)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.support.adapter.imap.models import ImapThreadMessage
from app.support.adapter.imap.normalize import ThreadHeaders
from app.support.adapter.mailbox_key import MailboxKey

INBOUND = "inbound"
OUTBOUND = "outbound"


class ImapThreadRepository:
    def __init__(self, db: Session):
        self.db = db

    def record_inbound(
        self,
        mailbox_key: MailboxKey,
        conversation_id: str,
        headers: ThreadHeaders,
        sender_address: str,
        subject: str | None,
        received_at: datetime,
    ) -> None:
        """Idempotent, so a re-fetch after a crash is a no-op: on (Mailbox, message_id),
        or for a message without a Message-ID on its Conversation, sender and time."""
        if headers.message_id is None and self._has_inbound_without_message_id(
            mailbox_key, conversation_id, sender_address, received_at
        ):
            return
        self._insert_if_absent(
            ImapThreadMessage(
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
                direction=INBOUND,
                message_id=headers.message_id,
                reference_ids=" ".join(headers.references) or None,
                sender_address=sender_address,
                subject=subject,
                message_at=received_at,
            )
        )

    def record_outbound(
        self,
        mailbox_key: MailboxKey,
        conversation_id: str,
        message_id: str,
        references: list[str],
        sender_address: str,
        subject: str,
        sent_at: datetime,
    ) -> None:
        self.db.add(
            ImapThreadMessage(
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
                direction=OUTBOUND,
                message_id=message_id,
                reference_ids=" ".join(references) or None,
                sender_address=sender_address,
                subject=subject,
                message_at=sent_at,
            )
        )
        self.db.commit()

    def find_by_message_id(
        self, mailbox_key: MailboxKey, message_id: str
    ) -> ImapThreadMessage | None:
        return (
            self.db.query(ImapThreadMessage)
            .filter_by(
                adapter=mailbox_key.adapter, mailbox=mailbox_key.mailbox, message_id=message_id
            )
            .one_or_none()
        )

    def conversation_of(self, mailbox_key: MailboxKey, message_ids: list[str]) -> str | None:
        """The Conversation of the first of `message_ids` recorded for this Mailbox,
        inbound or ours, or None."""
        if not message_ids:
            return None
        rows = (
            self.db.query(ImapThreadMessage.message_id, ImapThreadMessage.conversation_id)
            .filter(
                ImapThreadMessage.adapter == mailbox_key.adapter,
                ImapThreadMessage.mailbox == mailbox_key.mailbox,
                ImapThreadMessage.message_id.in_(message_ids),
            )
            .all()
        )
        conversations = dict(rows)
        return next((conversations[m] for m in message_ids if m in conversations), None)

    def is_sent_by_us(self, mailbox_key: MailboxKey, message_id: str | None) -> bool:
        if message_id is None:
            return False
        row = self.find_by_message_id(mailbox_key, message_id)
        return row is not None and row.direction == OUTBOUND

    def last_inbound(
        self, mailbox_key: MailboxKey, conversation_id: str
    ) -> ImapThreadMessage | None:
        return (
            self.db.query(ImapThreadMessage)
            .filter_by(
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
                direction=INBOUND,
            )
            .order_by(ImapThreadMessage.message_at.desc(), ImapThreadMessage.created_at.desc())
            .first()
        )

    def _has_inbound_without_message_id(
        self,
        mailbox_key: MailboxKey,
        conversation_id: str,
        sender_address: str,
        received_at: datetime,
    ) -> bool:
        return (
            self.db.query(ImapThreadMessage.id)
            .filter_by(
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
                direction=INBOUND,
                message_id=None,
                sender_address=sender_address,
                message_at=received_at,
            )
            .first()
            is not None
        )

    def _insert_if_absent(self, row: ImapThreadMessage) -> None:
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
