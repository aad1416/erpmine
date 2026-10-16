"""Validate and persist original support-email attachments."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import uuid
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.attachment_formats import MAX_EXTRACTED_TOKENS_PER_FILE
from app.config.email_attachments import (
    AUDIO_EXTENSIONS, EMAIL_DOCUMENT_IMAGE_EXTENSIONS,
    MAX_CONVERSATION_ATTACHMENTS_SIZE_BYTES, MAX_EMAIL_ATTACHMENTS_SIZE_BYTES,
    MAX_FILE_SIZE_BYTES, VIDEO_EXTENSIONS,
)
from app.config.setting import settings
from app.db.models.EmailAttachment import EmailAttachment
from app.repositories.email_attachments import EmailAttachmentRepository
from app.services.chat_attachment_processor import (
    AttachmentLimitError, AttachmentValidationError, ChatAttachmentProcessor,
)
from app.services.email_attachment_policy import (
    metadata_rejection, safe_file_name, stored_file_rejection,
)
from app.support.adapter.attachment_capture_port import AttachmentMetadata
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedAttachment
from app.utils.token_count import count_tokens

logger = logging.getLogger(__name__)


class EmailAttachmentCaptureService:
    def __init__(self, db: Session, *, processor: ChatAttachmentProcessor | None = None) -> None:
        self.db = db
        self.repository = EmailAttachmentRepository(db)
        self.processor = processor or ChatAttachmentProcessor()
        self.storage_path = Path(settings.file_storage_path or "storage") / "support_email_attachments"

    def existing_summary(
        self,
        mailbox_key: MailboxKey,
        external_message_id: str,
        external_attachment_id: str,
    ) -> NormalizedAttachment | None:
        row = self.repository.get_by_provider_identity(
            mailbox_key, external_message_id, external_attachment_id
        )
        return self.to_summary(row) if row else None

    def capture(
        self,
        *,
        mailbox_key: MailboxKey,
        conversation_id: str,
        external_message_id: str,
        candidate: AttachmentMetadata,
        data: bytes | None,
        position: int,
        message_bytes_already_accepted: int,
        download_error: str | None = None,
    ) -> NormalizedAttachment:
        existing = self.repository.get_by_provider_identity(
            mailbox_key, external_message_id, candidate.external_attachment_id
        )
        if existing:
            return self.to_summary(existing)

        file_name = safe_file_name(candidate.file_name)
        content_type = (
            candidate.content_type
            or mimetypes.guess_type(file_name)[0]
            or "application/octet-stream"
        ).split(";", 1)[0].strip().lower()
        if len(content_type) > 255 or any(ord(character) < 32 for character in content_type):
            content_type = "application/octet-stream"

        rejection = metadata_rejection(
            file_name=file_name,
            position=position,
            declared_size=candidate.declared_size,
            message_bytes_already_accepted=message_bytes_already_accepted,
        )
        if rejection:
            return self._record_without_file(
                mailbox_key=mailbox_key,
                conversation_id=conversation_id,
                external_message_id=external_message_id,
                candidate=candidate,
                file_name=file_name or "unnamed",
                content_type=content_type,
                status="rejected",
                reason=rejection,
            )
        if download_error or data is None:
            return self._record_without_file(
                mailbox_key=mailbox_key,
                conversation_id=conversation_id,
                external_message_id=external_message_id,
                candidate=candidate,
                file_name=file_name,
                content_type=content_type,
                status="unavailable",
                reason=download_error or "The attachment could not be downloaded.",
            )

        actual_size = len(data)
        rejection = self._content_rejection(
            file_name=file_name,
            data=data,
            message_bytes_already_accepted=message_bytes_already_accepted,
            conversation_bytes_already_accepted=self.repository.accepted_bytes_for_conversation(
                mailbox_key, conversation_id
            ),
        )
        if rejection:
            return self._record_without_file(
                mailbox_key=mailbox_key,
                conversation_id=conversation_id,
                external_message_id=external_message_id,
                candidate=candidate,
                file_name=file_name,
                content_type=content_type,
                status="rejected",
                reason=rejection,
                actual_size=actual_size,
            )

        self.storage_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.storage_path.chmod(0o700)
        attachment_id = str(uuid.uuid4())
        extension = Path(file_name).suffix.lower().lstrip(".") or "bin"
        final_path = self.storage_path / f"{attachment_id}.{extension}"
        staged_path = self.storage_path / f".{attachment_id}.uploading"
        try:
            descriptor = os.open(staged_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            staged_path.replace(final_path)

            row = EmailAttachment(
                id=attachment_id,
                adapter=mailbox_key.adapter,
                mailbox=mailbox_key.mailbox,
                conversation_id=conversation_id,
                external_message_id=external_message_id,
                external_attachment_id=candidate.external_attachment_id,
                file_name=file_name,
                content_type=content_type,
                size=actual_size,
                sha256=hashlib.sha256(data).hexdigest(),
                storage_path=str(final_path),
                capture_status="ready",
                kind="opaque",
                ai_status="unsupported",
                ticket_status="pending",
            )
            validation_error = self._classify_and_extract(row, final_path, extension)
            if validation_error:
                final_path.unlink(missing_ok=True)
                return self._record_without_file(
                    mailbox_key=mailbox_key,
                    conversation_id=conversation_id,
                    external_message_id=external_message_id,
                    candidate=candidate,
                    file_name=file_name,
                    content_type=content_type,
                    status="rejected",
                    reason=validation_error,
                    actual_size=actual_size,
                )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            return self.to_summary(row)
        except Exception:
            self.db.rollback()
            staged_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise

    def list_for_conversation(
        self, mailbox_key: MailboxKey, conversation_id: str
    ) -> list[EmailAttachment]:
        return self.repository.list_for_conversation(mailbox_key, conversation_id)

    def preflight_rejection(
        self,
        candidate: AttachmentMetadata,
        *,
        position: int,
        message_bytes_already_accepted: int,
    ) -> str | None:
        """Reject from provider metadata before downloading bytes when possible."""
        return metadata_rejection(
            file_name=safe_file_name(candidate.file_name),
            position=position,
            declared_size=candidate.declared_size,
            message_bytes_already_accepted=message_bytes_already_accepted,
        )

    def stored_file_rejection(self, attachment: EmailAttachment) -> str | None:
        """Apply the current file policy to a row captured by an older code version."""
        return stored_file_rejection(attachment.file_name, attachment.size)

    @staticmethod
    def to_summary(row: EmailAttachment) -> NormalizedAttachment:
        return NormalizedAttachment(
            id=row.id,
            external_attachment_id=row.external_attachment_id,
            file_name=row.file_name,
            content_type=row.content_type,
            size=row.size,
            capture_status=row.capture_status,
            capture_error=row.capture_error,
            kind=row.kind,
            ai_status=row.ai_status,
        )

    @staticmethod
    def _content_rejection(
        *,
        file_name: str,
        data: bytes,
        message_bytes_already_accepted: int,
        conversation_bytes_already_accepted: int,
    ) -> str | None:
        size = len(data)
        if size == 0:
            return "The attachment is empty."
        if size > MAX_FILE_SIZE_BYTES:
            return "The attachment exceeds the 20 MiB per-file limit."
        if message_bytes_already_accepted + size > MAX_EMAIL_ATTACHMENTS_SIZE_BYTES:
            return "The email exceeds the 25 MiB combined attachment limit."
        if conversation_bytes_already_accepted + size > MAX_CONVERSATION_ATTACHMENTS_SIZE_BYTES:
            return "The conversation exceeds the 50 MiB attachment limit."
        if EmailAttachmentCaptureService._looks_executable(data):
            return "The attachment contains executable program data and is blocked for safety."

        return None

    def _record_without_file(
        self,
        *,
        mailbox_key: MailboxKey,
        conversation_id: str,
        external_message_id: str,
        candidate: AttachmentMetadata,
        file_name: str,
        content_type: str,
        status: str,
        reason: str,
        actual_size: int | None = None,
    ) -> NormalizedAttachment:
        row = EmailAttachment(
            adapter=mailbox_key.adapter,
            mailbox=mailbox_key.mailbox,
            conversation_id=conversation_id,
            external_message_id=external_message_id,
            external_attachment_id=candidate.external_attachment_id,
            file_name=file_name,
            content_type=content_type,
            size=actual_size if actual_size is not None else max(candidate.declared_size, 0),
            capture_status=status,
            capture_error=reason,
            kind="opaque",
            ai_status="unsupported",
            ticket_status="rejected",
            ticket_error=reason,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_summary(row)

    def _classify_and_extract(
        self, row: EmailAttachment, path: Path, extension: str
    ) -> str | None:
        # MIME disambiguates .webm, which can contain either audio or video. If an
        # unknown MIME is supplied, default ambiguous .webm evidence to video/human
        # review rather than trying to transcribe a video container as audio.
        if extension == "webm" and row.content_type.startswith("audio/"):
            if not self._valid_media_signature(path, extension):
                return "The file extension does not match its audio or video content."
            row.kind = "audio"
            row.content_type = "audio/webm"
            row.ai_status = "pending"
            return None
        if extension in VIDEO_EXTENSIONS:
            if not self._valid_media_signature(path, extension):
                return "The file extension does not match its audio or video content."
            row.kind = "video"
            row.content_type = mimetypes.guess_type(row.file_name)[0] or "video/mp4"
            row.ai_status = "unsupported"
            return None
        if extension in AUDIO_EXTENSIONS:
            if not self._valid_media_signature(path, extension):
                return "The file extension does not match its audio or video content."
            row.kind = "audio"
            row.content_type = mimetypes.guess_type(row.file_name)[0] or "audio/mpeg"
            row.ai_status = "pending"
            return None
        if extension not in EMAIL_DOCUMENT_IMAGE_EXTENSIONS:
            return "This file type is not accepted for email attachments."
        if extension in {"docx", "xlsx"}:
            try:
                with zipfile.ZipFile(path) as archive:
                    names = (name.casefold().replace("\\", "/") for name in archive.namelist())
                    if any(
                        name.endswith("/vbaproject.bin")
                        or "/activex/" in name
                        or "/embeddings/" in name
                        for name in names
                    ):
                        return "Office files with macros or embedded active objects are blocked."
            except (OSError, zipfile.BadZipFile):
                return "The Office file is invalid or unreadable."
        if self._extract_utf16_text(row, path, extension):
            if row.ai_status == "ready":
                row.content_type = mimetypes.guess_type(row.file_name)[0] or "text/plain"
            return row.capture_error if row.ai_status == "failed" else None
        try:
            processed = self.processor.process(path, row.file_name)
        except AttachmentLimitError as exc:
            row.kind = "document"
            row.ai_status = "failed"
            row.capture_error = f"AI processing skipped: {exc}"
            row.content_type = mimetypes.guess_type(row.file_name)[0] or row.content_type
            return None
        except AttachmentValidationError as exc:
            return f"The file is invalid or unreadable: {exc}"
        except Exception as exc:
            logger.exception("Email attachment validation failed for %s", row.file_name)
            return f"The file could not be validated: {type(exc).__name__}"

        row.kind = processed.kind
        row.content_type = processed.mime_type
        row.extracted_text = processed.extracted_text
        row.token_count = processed.token_count
        row.ai_status = "ready" if processed.extracted_text else "pending"
        return None

    @staticmethod
    def _extract_utf16_text(row: EmailAttachment, path: Path, extension: str) -> bool:
        """Handle BOM-marked text without changing the original ticket evidence."""
        if extension not in {"txt", "md", "csv"}:
            return False
        with path.open("rb") as handle:
            if handle.read(2) not in {b"\xff\xfe", b"\xfe\xff"}:
                return False

        row.kind = "document"
        try:
            text = path.read_bytes().decode("utf-16").strip()
        except UnicodeDecodeError:
            row.ai_status = "failed"
            row.capture_error = "AI processing failed: The UTF-16 text file is invalid."
            return True
        controls = sum(
            character not in {"\n", "\r", "\t"} and ord(character) < 32
            for character in text
        )
        if not text or controls / len(text) > 0.01:
            row.ai_status = "failed"
            row.capture_error = "AI processing failed: The text file contains binary data."
            return True
        tokens = count_tokens(text)
        if tokens > MAX_EXTRACTED_TOKENS_PER_FILE:
            row.ai_status = "failed"
            row.capture_error = "AI processing skipped: The text exceeds the per-file token limit."
            return True
        row.extracted_text = text
        row.token_count = tokens
        row.ai_status = "ready"
        row.capture_error = None
        return True

    @staticmethod
    def _looks_executable(data: bytes) -> bool:
        return (
            data.startswith(b"MZ")
            or data.startswith(b"\x7fELF")
            or data[:4]
            in {
                b"\xfe\xed\xfa\xce",
                b"\xfe\xed\xfa\xcf",
                b"\xce\xfa\xed\xfe",
                b"\xcf\xfa\xed\xfe",
            }
        )

    @staticmethod
    def _valid_media_signature(path: Path, extension: str) -> bool:
        """Reject obvious renamed files before STT or ticket upload."""
        with path.open("rb") as handle:
            header = handle.read(16)
        if extension in {"m4a", "mp4", "mov"}:
            return len(header) >= 12 and header[4:8] == b"ftyp"
        if extension in {"wav", "avi"}:
            expected = b"WAVE" if extension == "wav" else b"AVI "
            return header.startswith(b"RIFF") and header[8:12] == expected
        if extension in {"ogg"}:
            return header.startswith(b"OggS")
        if extension == "flac":
            return header.startswith(b"fLaC")
        if extension == "webm":
            return header.startswith(b"\x1a\x45\xdf\xa3")
        if extension == "mp3":
            return header.startswith(b"ID3") or (
                len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
            )
        if extension == "aac":
            return header.startswith(b"ADIF") or (
                len(header) >= 2 and header[0] == 0xFF and header[1] & 0xF6 == 0xF0
            )
        if extension in {"mpeg", "mpg"}:
            return header.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"))
        return False
