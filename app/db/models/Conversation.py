import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class Conversation(Base):
    """Per-conversation derived state for the support decision agent (02-architecture-decisions.md §10.1)."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "adapter",
            "mailbox",
            "conversation_id",
            name="uq_conversation_adapter_mailbox_conversation_id",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    adapter = Column(String, nullable=False)
    mailbox = Column(String, nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True)

    unit_serial = Column(String, nullable=True)
    issue_description = Column(String, nullable=True)
    question_round_count = Column(Integer, nullable=False, default=0)
    serial_correction_attempt_count = Column(Integer, nullable=False, default=0)
    ticket_id = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    messages = relationship(
        "ConversationMessage", back_populates="conversation", cascade="all, delete-orphan"
    )
