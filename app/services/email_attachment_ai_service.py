"""Prepare captured email evidence for the support AI."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from openai import AsyncOpenAI, NotFoundError
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.models.EmailAttachment import EmailAttachment
from app.services.email_attachment_policy import stored_file_rejection
from app.utils.token_count import count_tokens

logger = logging.getLogger(__name__)


class EmailAttachmentUnavailableError(RuntimeError):
    pass


class EmailAttachmentAIService:
    def __init__(
        self,
        db: Session,
        *,
        openai_client_factory: Callable[[], AsyncOpenAI] | None = None,
        stt_factory: Callable[[], object] | None = None,
    ) -> None:
        self.db = db
        self._openai_client_factory = openai_client_factory or self._make_openai_client
        self._stt_factory = stt_factory or self._make_stt_service

    @staticmethod
    def manifest(attachments: Sequence[EmailAttachment]) -> str:
        if not attachments:
            return ""
        lines = [
            "Customer files, including named inline files (assume they are probably related "
            "evidence even when their names are generic; all accepted originals will be "
            "forwarded to the ticket):"
        ]
        for attachment in attachments:
            details = [
                f"id={attachment.id}",
                f"name={attachment.file_name!r}",
                f"type={attachment.content_type}",
                f"size={attachment.size} bytes",
                f"capture={attachment.capture_status}",
                f"ai={attachment.ai_status}",
            ]
            if attachment.kind == "video":
                details.append("video requires human review; you cannot watch it")
            if attachment.capture_error:
                details.append(f"reason={attachment.capture_error}")
            lines.append("- " + "; ".join(details))
        return "\n".join(lines)

    async def read_text(self, attachment: EmailAttachment) -> str:
        if attachment.capture_status != "ready":
            return attachment.capture_error or "This attachment is unavailable."
        if rejection := stored_file_rejection(attachment.file_name, attachment.size):
            return rejection
        if attachment.kind == "video":
            return (
                "This is a video. The current support AI cannot watch or interpret video. "
                "The original will still be attached to the ticket for human review."
            )
        if attachment.kind == "audio":
            if attachment.ai_status == "ready" and attachment.extracted_text:
                return attachment.extracted_text
            if attachment.ai_status == "failed":
                return (
                    "The audio could not be transcribed. The original will still be "
                    "attached to the ticket for human review."
                )
            await self._transcribe_audio(attachment)
            return attachment.extracted_text or (
                "The audio contained no usable English speech. The original will still "
                "be attached to the ticket for human review."
            )
        if attachment.extracted_text:
            return attachment.extracted_text
        return (
            "The current support AI cannot read this file type. The original will still "
            "be attached to the ticket for human review."
        )

    async def ensure_openai_file(self, attachment: EmailAttachment) -> str:
        if rejection := stored_file_rejection(attachment.file_name, attachment.size):
            raise EmailAttachmentUnavailableError(rejection)
        if attachment.kind not in {"image", "pdf_scanned", "pdf_mixed"}:
            raise EmailAttachmentUnavailableError(
                "This attachment does not support visual inspection."
            )
        path = self._require_local_file(attachment)
        client = self._openai_client_factory()
        if attachment.openai_file_id:
            try:
                await client.files.retrieve(attachment.openai_file_id)
                return attachment.openai_file_id
            except NotFoundError:
                attachment.openai_file_id = None
            except Exception as exc:
                raise EmailAttachmentUnavailableError(
                    "The attachment could not be prepared for visual inspection."
                ) from exc

        purpose = "vision" if attachment.kind == "image" else "user_data"
        try:
            with path.open("rb") as handle:
                uploaded = await client.files.create(
                    file=handle,
                    purpose=purpose,
                )
        except Exception as exc:
            logger.exception("Failed to upload email attachment %s to OpenAI", attachment.id)
            raise EmailAttachmentUnavailableError(
                "The attachment could not be prepared for visual inspection."
            ) from exc

        attachment.openai_file_id = uploaded.id
        self.db.commit()
        return uploaded.id

    async def delete_openai_copy(self, file_id: str | None) -> bool:
        if not file_id:
            return True
        try:
            await self._openai_client_factory().files.delete(file_id)
            return True
        except NotFoundError:
            return True
        except Exception:
            # Keep the reference so the daily cleanup can retry after a provider or
            # configuration outage. Canonical evidence is never affected.
            logger.warning("Could not delete inactive OpenAI file %s", file_id, exc_info=True)
            return False

    async def _transcribe_audio(self, attachment: EmailAttachment) -> None:
        path = self._require_local_file(attachment)
        try:
            transcript = await asyncio.to_thread(
                self._stt_factory().transcribe,
                path.read_bytes(),
                attachment.file_name,
            )
            attachment.extracted_text = transcript.strip()
            attachment.token_count = count_tokens(attachment.extracted_text)
            attachment.ai_status = "ready"
            attachment.capture_error = None
        except Exception as exc:
            logger.warning(
                "Could not transcribe email attachment %s", attachment.id, exc_info=True
            )
            attachment.ai_status = "failed"
            attachment.capture_error = f"Audio transcription failed: {type(exc).__name__}"
        self.db.commit()

    @staticmethod
    def _require_local_file(attachment: EmailAttachment) -> Path:
        path = Path(attachment.storage_path or "")
        if not attachment.storage_path or not path.is_file():
            raise EmailAttachmentUnavailableError(
                "The stored attachment is no longer available for AI inspection."
            )
        return path

    @staticmethod
    def _make_openai_client() -> AsyncOpenAI:
        if not settings.OPENAI_API_KEY:
            raise EmailAttachmentUnavailableError(
                "OpenAI is not configured for visual attachment inspection."
            )
        return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @staticmethod
    def _make_stt_service():
        from app.services.stt_service import STTService

        return STTService(provider="openai", model="whisper-1")
