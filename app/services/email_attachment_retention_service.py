"""Clean up local originals and temporary OpenAI copies."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.repositories.email_attachments import EmailAttachmentRepository
from app.db.models.EmailAttachment import EmailAttachment

logger = logging.getLogger(__name__)


class EmailAttachmentRetentionService:
    def __init__(
        self, db: Session, *, delete_openai_file: Callable[[str | None], Awaitable[bool]]
    ) -> None:
        self.db = db
        self.repository = EmailAttachmentRepository(db)
        self._delete_openai_file = delete_openai_file

    def delete_uploaded_local_file(self, attachment: EmailAttachment) -> bool:
        """Remove the local original only after ticket upload is committed."""
        if attachment.ticket_status != "uploaded" or not attachment.storage_path:
            return False
        try:
            Path(attachment.storage_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete uploaded email attachment %s", attachment.id, exc_info=True)
            return False
        attachment.storage_path = None
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.warning(
                "Could not record deletion of uploaded email attachment %s",
                attachment.id, exc_info=True,
            )
            return False
        return True

    def purge_uploaded_local_files(self) -> int:
        """Finish deletions left behind if a process stopped after upload commit."""
        deleted = 0
        for attachment in self.repository.list_uploaded_with_local_files():
            deleted += self.delete_uploaded_local_file(attachment)
        return deleted

    def purge_expired_unuploaded_local_files(self, retention_days: int) -> int:
        """Expire local bytes that never reached a ticket within the retention period."""
        deleted = 0
        for attachment in self.repository.list_expired_unuploaded_local_files(retention_days):
            try:
                Path(attachment.storage_path).unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not delete expired email attachment %s", attachment.id, exc_info=True)
                continue
            attachment.storage_path = None
            attachment.capture_status = "unavailable"
            attachment.capture_error = "The attachment expired before it could be added to a ticket."
            attachment.ticket_status = "rejected"
            attachment.ticket_error = attachment.capture_error
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.warning(
                    "Could not record expiry of email attachment %s",
                    attachment.id, exc_info=True,
                )
                continue
            deleted += 1
        return deleted

    async def purge_inactive_openai_files(self, inactivity_days: int) -> int:
        """Delete only OpenAI copies after conversation inactivity.

        Canonical customer evidence and derived text remain untouched. If the
        conversation becomes active later, ensure_openai_file can upload the canonical
        file again.
        """
        purged = 0
        attachments = self.repository.list_openai_files_for_inactive_conversations(
            inactivity_days
        )
        for attachment in attachments:
            if await self._delete_openai_file(attachment.openai_file_id):
                attachment.openai_file_id = None
                purged += 1
        self.db.commit()
        return purged
