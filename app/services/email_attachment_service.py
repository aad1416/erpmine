"""Compatibility facade for support-email attachment operations.

Capture, AI preparation, and retention have separate implementations. New adapter
code uses the capture port rather than this broad service.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.db.models.EmailAttachment import EmailAttachment
from app.services.chat_attachment_processor import ChatAttachmentProcessor
from app.services.email_attachment_ai_service import (
    EmailAttachmentAIService, EmailAttachmentUnavailableError,
)
from app.services.email_attachment_capture_service import EmailAttachmentCaptureService
from app.services.email_attachment_retention_service import EmailAttachmentRetentionService
from app.support.adapter.attachment_capture_port import AttachmentMetadata
from app.support.adapter.attachment_candidates import AttachmentCandidate
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedAttachment


class EmailAttachmentService:
    def __init__(
        self,
        db: Session,
        *,
        processor: ChatAttachmentProcessor | None = None,
        openai_client_factory: Callable[[], AsyncOpenAI] | None = None,
        stt_factory: Callable[[], object] | None = None,
    ) -> None:
        self.capture_service = EmailAttachmentCaptureService(db, processor=processor)
        self.ai_service = EmailAttachmentAIService(
            db,
            openai_client_factory=openai_client_factory, stt_factory=stt_factory,
        )
        self.retention_service = EmailAttachmentRetentionService(
            db, delete_openai_file=self.ai_service.delete_openai_copy,
        )
        self.repository = self.capture_service.repository

    def existing_summary(
        self, mailbox_key: MailboxKey, external_message_id: str, external_attachment_id: str
    ) -> NormalizedAttachment | None:
        return self.capture_service.existing_summary(
            mailbox_key, external_message_id, external_attachment_id
        )

    def capture(
        self, *, mailbox_key: MailboxKey, conversation_id: str, external_message_id: str,
        candidate: AttachmentCandidate, data: bytes | None, position: int,
        message_bytes_already_accepted: int, download_error: str | None = None,
    ) -> NormalizedAttachment:
        return self.capture_service.capture(
            mailbox_key=mailbox_key, conversation_id=conversation_id,
            external_message_id=external_message_id,
            candidate=AttachmentMetadata.from_candidate(candidate), data=data,
            position=position, message_bytes_already_accepted=message_bytes_already_accepted,
            download_error=download_error,
        )

    def preflight_rejection(
        self, candidate: AttachmentCandidate, *, position: int,
        message_bytes_already_accepted: int,
    ) -> str | None:
        return self.capture_service.preflight_rejection(
            AttachmentMetadata.from_candidate(candidate), position=position,
            message_bytes_already_accepted=message_bytes_already_accepted,
        )

    def list_for_conversation(
        self, mailbox_key: MailboxKey, conversation_id: str
    ) -> list[EmailAttachment]:
        return self.capture_service.list_for_conversation(mailbox_key, conversation_id)

    def stored_file_rejection(self, attachment: EmailAttachment) -> str | None:
        return self.capture_service.stored_file_rejection(attachment)

    @staticmethod
    def manifest(attachments: Sequence[EmailAttachment]) -> str:
        return EmailAttachmentAIService.manifest(attachments)

    async def read_text(self, attachment: EmailAttachment) -> str:
        return await self.ai_service.read_text(attachment)

    async def ensure_openai_file(self, attachment: EmailAttachment) -> str:
        return await self.ai_service.ensure_openai_file(attachment)

    def delete_uploaded_local_file(self, attachment: EmailAttachment) -> bool:
        return self.retention_service.delete_uploaded_local_file(attachment)

    def purge_uploaded_local_files(self) -> int:
        return self.retention_service.purge_uploaded_local_files()

    def purge_expired_unuploaded_local_files(self, retention_days: int) -> int:
        return self.retention_service.purge_expired_unuploaded_local_files(retention_days)

    async def purge_inactive_openai_files(self, inactivity_days: int) -> int:
        return await self.retention_service.purge_inactive_openai_files(inactivity_days)
