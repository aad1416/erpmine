"""Adapter-facing contract for capturing email attachments.

Only provider metadata, bytes, mailbox identity, and normalized summaries cross this
boundary. The factory is the single binding to today's in-process implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.support.adapter.attachment_candidates import AttachmentCandidate
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedAttachment

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AttachmentMetadata:
    external_attachment_id: str
    file_name: str
    content_type: str
    declared_size: int = 0

    @classmethod
    def from_candidate(cls, candidate: AttachmentCandidate) -> AttachmentMetadata:
        return cls(
            candidate.external_attachment_id, candidate.file_name,
            candidate.content_type, candidate.declared_size,
        )


class AttachmentCapturePort(Protocol):
    async def existing_summary(
        self, mailbox_key: MailboxKey, external_message_id: str, external_attachment_id: str
    ) -> NormalizedAttachment | None: ...

    async def preflight_rejection(
        self, candidate: AttachmentMetadata, *, position: int,
        message_bytes_already_accepted: int,
    ) -> str | None: ...

    async def capture(
        self, *, mailbox_key: MailboxKey, conversation_id: str, external_message_id: str,
        candidate: AttachmentMetadata, data: bytes | None, position: int,
        message_bytes_already_accepted: int, download_error: str | None = None,
    ) -> NormalizedAttachment: ...


class AttachmentCaptureFactory(Protocol):
    def __call__(self, db: Session) -> AttachmentCapturePort: ...


def make_attachment_capture(db: Session) -> AttachmentCapturePort:
    """Bind the port to local persistence; replace this binding for remote capture."""
    from app.services.email_attachment_capture_port_impl import LocalAttachmentCapturePort

    return LocalAttachmentCapturePort(db)
