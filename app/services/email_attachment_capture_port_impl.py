"""In-process implementation of the adapter's asynchronous capture port."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.email_attachment_capture_service import EmailAttachmentCaptureService
from app.support.adapter.attachment_capture_port import AttachmentMetadata
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedAttachment


class LocalAttachmentCapturePort:
    def __init__(self, db: Session) -> None:
        self._service = EmailAttachmentCaptureService(db)

    async def existing_summary(
        self, mailbox_key: MailboxKey, external_message_id: str, external_attachment_id: str
    ) -> NormalizedAttachment | None:
        return self._service.existing_summary(
            mailbox_key, external_message_id, external_attachment_id
        )

    async def preflight_rejection(
        self, candidate: AttachmentMetadata, *, position: int,
        message_bytes_already_accepted: int,
    ) -> str | None:
        return self._service.preflight_rejection(
            candidate, position=position,
            message_bytes_already_accepted=message_bytes_already_accepted,
        )

    async def capture(
        self, *, mailbox_key: MailboxKey, conversation_id: str, external_message_id: str,
        candidate: AttachmentMetadata, data: bytes | None, position: int,
        message_bytes_already_accepted: int, download_error: str | None = None,
    ) -> NormalizedAttachment:
        return self._service.capture(
            mailbox_key=mailbox_key, conversation_id=conversation_id,
            external_message_id=external_message_id, candidate=candidate, data=data,
            position=position, message_bytes_already_accepted=message_bytes_already_accepted,
            download_error=download_error,
        )
