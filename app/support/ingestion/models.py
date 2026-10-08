import enum
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, Integer, JSON, Index, UniqueConstraint

from app.db.database import Base


class TaskType(str, enum.Enum):
    message = "message"
    create_ticket = "create_ticket"
    send_message = "send_message"
    # Never claimed: only used for synthesized dead-lettered escalation audit rows.
    ask_question = "ask_question"


class TaskStatus(str, enum.Enum):
    open = "open"
    running = "running"
    done = "done"
    error = "error"
    dead_letter = "dead_letter"


class IngestionTask(Base):
    """Database-backed task queue (03-ingestion-service-design.md §3)."""

    __tablename__ = "ingestion_tasks"
    __table_args__ = (
        Index("ix_ingestion_tasks_status_conversation", "status", "conversation_id"),
        # Makes the message sink idempotent: an adapter that hands the same message over
        # again (e.g. re-sinking an outbox row after a crash) gets no second task row.
        # NULL external_message_id (every non-message task) is exempt from this
        # constraint under SQLite/Postgres NULL semantics, so it never applies to the
        # synthesized dead_letter escalation markers.
        UniqueConstraint(
            "task_type",
            "adapter",
            "mailbox",
            "external_message_id",
            name="uq_ingestion_task_adapter_mailbox_dedup",
        ),
        Index(
            "ix_ingestion_tasks_adapter_mailbox_conversation",
            "adapter",
            "mailbox",
            "conversation_id",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String, nullable=False, index=True)
    adapter = Column(String, nullable=False)
    mailbox = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False, index=True)
    external_message_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default=TaskStatus.open.value, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    heartbeat_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

