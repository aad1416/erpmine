from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.db.models.Conversation import Conversation
from app.db.models.ConversationMessage import ConversationMessage
from app.db.models.EmailAttachment import EmailAttachment
from app.support.adapter.mailbox_key import MailboxKey


class EmailAttachmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_provider_identity(
        self, mailbox_key: MailboxKey, external_message_id: str, external_attachment_id: str
    ) -> EmailAttachment | None:
        return (
            self.db.query(EmailAttachment)
            .filter(
                EmailAttachment.adapter == mailbox_key.adapter,
                EmailAttachment.mailbox == mailbox_key.mailbox,
                EmailAttachment.external_message_id == external_message_id,
                EmailAttachment.external_attachment_id == external_attachment_id,
            )
            .first()
        )

    def get_by_id(self, attachment_id: str) -> EmailAttachment | None:
        return self.db.get(EmailAttachment, attachment_id)

    def list_for_conversation(
        self, mailbox_key: MailboxKey, conversation_id: str
    ) -> list[EmailAttachment]:
        return (
            self.db.query(EmailAttachment)
            .filter(
                EmailAttachment.adapter == mailbox_key.adapter,
                EmailAttachment.mailbox == mailbox_key.mailbox,
                EmailAttachment.conversation_id == conversation_id,
            )
            .order_by(EmailAttachment.created_at.asc())
            .all()
        )

    def accepted_bytes_for_conversation(self, mailbox_key: MailboxKey, conversation_id: str) -> int:
        """Lifetime accepted bytes; metadata survives local-file retention cleanup."""
        rows = self.list_for_conversation(mailbox_key, conversation_id)
        return sum(row.size for row in rows if row.sha256 is not None)

    def list_waiting_for_ticket(
        self, mailbox_key: MailboxKey, conversation_id: str
    ) -> list[EmailAttachment]:
        return (
            self.db.query(EmailAttachment)
            .filter(
                EmailAttachment.adapter == mailbox_key.adapter,
                EmailAttachment.mailbox == mailbox_key.mailbox,
                EmailAttachment.conversation_id == conversation_id,
                EmailAttachment.capture_status == "ready",
                EmailAttachment.ticket_status == "pending",
            )
            .order_by(EmailAttachment.created_at.asc())
            .all()
        )

    def list_uploaded_with_local_files(self) -> list[EmailAttachment]:
        return (
            self.db.query(EmailAttachment)
            .filter(
                EmailAttachment.ticket_status == "uploaded",
                EmailAttachment.storage_path.isnot(None),
            )
            .all()
        )

    def list_expired_unuploaded_local_files(self, retention_days: int) -> list[EmailAttachment]:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        return (
            self.db.query(EmailAttachment)
            .filter(
                EmailAttachment.ticket_status != "uploaded",
                EmailAttachment.storage_path.isnot(None),
                EmailAttachment.created_at < cutoff,
            )
            .all()
        )

    def list_openai_files_for_inactive_conversations(
        self, inactivity_days: int
    ) -> list[EmailAttachment]:
        """Find provider copies whose conversations have no recent activity.

        Message.created_at is the local activity time, so a newly processed old provider
        message is not immediately considered inactive. Attachment.updated_at also
        protects a provider copy uploaded recently for an older thread.
        """
        cutoff = datetime.now(UTC) - timedelta(days=inactivity_days)
        latest_message = (
            self.db.query(
                ConversationMessage.conversation_id.label("conversation_pk"),
                func.max(ConversationMessage.created_at).label("last_activity_at"),
            )
            .group_by(ConversationMessage.conversation_id)
            .subquery()
        )
        return (
            self.db.query(EmailAttachment)
            .join(
                Conversation,
                and_(
                    Conversation.adapter == EmailAttachment.adapter,
                    Conversation.mailbox == EmailAttachment.mailbox,
                    Conversation.conversation_id == EmailAttachment.conversation_id,
                ),
            )
            .outerjoin(
                latest_message,
                latest_message.c.conversation_pk == Conversation.id,
            )
            .filter(
                EmailAttachment.openai_file_id.isnot(None),
                EmailAttachment.updated_at < cutoff,
                or_(
                    latest_message.c.last_activity_at < cutoff,
                    and_(
                        latest_message.c.last_activity_at.is_(None),
                        Conversation.updated_at < cutoff,
                    ),
                ),
            )
            .all()
        )

    def mark_uploaded(
        self, attachment: EmailAttachment, ticket_id: str, ticket_file_id: str | None
    ) -> None:
        attachment.ticket_id = ticket_id
        attachment.ticket_status = "uploaded"
        attachment.ticket_file_id = ticket_file_id
        attachment.ticket_error = None
        attachment.ticket_uploaded_at = datetime.now(UTC)
        self.db.commit()

    def mark_ticket_rejected(
        self, attachment: EmailAttachment, ticket_id: str, reason: str
    ) -> None:
        attachment.ticket_id = ticket_id
        attachment.ticket_status = "rejected"
        attachment.ticket_error = reason
        self.db.commit()
