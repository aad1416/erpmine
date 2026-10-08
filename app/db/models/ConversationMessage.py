import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class ConversationMessage(Base):
    """Durable, conversation-scoped staging log — the source of truth before a ticket
    exists, and the record backfilled into the official Communication Log once one does
    (02-architecture-decisions.md §8, §9.3)."""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "external_message_id", name="uq_conversation_message_dedup"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(
        String(36), ForeignKey("conversations.id"), nullable=False, index=True
    )
    external_message_id = Column(String, nullable=True)
    sender_address = Column(String, nullable=True)
    direction = Column(String, nullable=False)  # "inbound" | "outbound"
    body_text = Column(String, nullable=False)
    received_at = Column(DateTime, nullable=False)
    synced_to_ticket_log = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    conversation = relationship("Conversation", back_populates="messages")
