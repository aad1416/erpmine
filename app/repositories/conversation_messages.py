from datetime import datetime, UTC
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.Conversation import Conversation
from app.db.models.ConversationMessage import ConversationMessage
from app.support.adapter.schemas import NormalizedMessage


class ConversationMessageRepository:
    """The durable, conversation-scoped staging log — source of truth before a ticket
    exists (02-architecture-decisions.md §8, §9.3)."""

    def __init__(self, db: Session):
        self.db = db

    def add_inbound(
        self, conversation: Conversation, messages: List[NormalizedMessage]
    ) -> List[ConversationMessage]:
        rows = []
        for message in messages:
            row = ConversationMessage(
                conversation_id=conversation.id,
                external_message_id=message.external_message_id,
                sender_address=message.sender_address,
                direction="inbound",
                body_text=message.body_text,
                received_at=message.received_at,
            )
            self.db.add(row)
            try:
                self.db.commit()
                self.db.refresh(row)
                rows.append(row)
            except IntegrityError:
                self.db.rollback()
        return rows

    def add_outbound(
        self, conversation: Conversation, text: str, commit: bool = True
    ) -> ConversationMessage:
        """`commit=False` leaves the row pending so the caller can commit it together
        with related writes in one transaction (see conversation_service's
        handle_create_ticket_task, where a partial commit would strand a ticket_id with
        no queued reply)."""
        row = ConversationMessage(
            conversation_id=conversation.id,
            direction="outbound",
            body_text=text,
            received_at=datetime.now(UTC),
        )
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        return row

    def get_all(self, conversation_id: str) -> List[ConversationMessage]:
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.received_at.asc())
            .all()
        )

    def get_unsynced(self, conversation_id: str) -> List[ConversationMessage]:
        return (
            self.db.query(ConversationMessage)
            .filter(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.synced_to_ticket_log.is_(False),
            )
            .order_by(ConversationMessage.received_at.asc())
            .all()
        )
