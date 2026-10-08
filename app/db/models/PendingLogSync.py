import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, UniqueConstraint

from app.db.database import Base


class PendingLogSync(Base):
    """Retry-with-backoff queue for backfilling ConversationMessage rows into the
    official Communication Log once a ticket exists (02-architecture-decisions.md §8)."""

    __tablename__ = "pending_log_syncs"
    __table_args__ = (
        UniqueConstraint("conversation_message_id", name="uq_pending_log_sync_message"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String, nullable=False, index=True)
    conversation_message_id = Column(
        String(36), ForeignKey("conversation_messages.id"), nullable=False
    )
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    status = Column(String, nullable=False, default="pending")  # pending | done | dead_letter
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
