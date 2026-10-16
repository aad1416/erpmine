from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.db.database import Base


class EmailAttachment(Base):
    """Canonical copy and delivery state for one explicit inbound email attachment."""

    __tablename__ = "email_attachments"
    __table_args__ = (
        UniqueConstraint(
            "adapter",
            "mailbox",
            "external_message_id",
            "external_attachment_id",
            name="uq_email_attachment_provider_identity",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    adapter = Column(String, nullable=False)
    mailbox = Column(String, nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True)
    external_message_id = Column(String, nullable=False, index=True)
    external_attachment_id = Column(String, nullable=False)

    file_name = Column(String(255), nullable=False)
    content_type = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False, default=0)
    sha256 = Column(String(64), nullable=True)
    storage_path = Column(Text, nullable=True)

    capture_status = Column(String(24), nullable=False)
    capture_error = Column(Text, nullable=True)
    kind = Column(String(24), nullable=False, default="opaque")
    ai_status = Column(String(24), nullable=False, default="unsupported")
    extracted_text = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=False, default=0)

    ticket_id = Column(String, nullable=True, index=True)
    ticket_status = Column(String(24), nullable=False, default="pending")
    ticket_file_id = Column(String, nullable=True)
    ticket_error = Column(Text, nullable=True)
    ticket_uploaded_at = Column(DateTime(timezone=True), nullable=True)

    openai_file_id = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
