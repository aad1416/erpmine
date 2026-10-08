"""Wraps the Communication Log API (append-only — no edit endpoint,
04-ticket-api-contracts.md §3-4) and the backfill staging logic (§8): the API requires an
existing ticket ID, so pre-ticket Q&A is staged in ConversationMessage and backfilled here
once a ticket exists.
"""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.models.Conversation import Conversation
from app.db.models.PendingLogSync import PendingLogSync
from app.repositories.conversation_messages import ConversationMessageRepository

logger = logging.getLogger(__name__)


def enqueue_backfill(
    db: Session, conversation: Conversation, ticket_id: str, commit: bool = True
) -> None:
    """Stages every not-yet-synced ConversationMessage for this conversation as a
    PendingLogSync row, to be drained by log_sync_retry_job.py. `commit=False` defers to
    a caller-owned transaction."""
    unsynced = ConversationMessageRepository(db).get_unsynced(conversation.id)
    for message in unsynced:
        db.add(PendingLogSync(ticket_id=ticket_id, conversation_message_id=message.id))
    if commit:
        db.commit()


class CommunicationLogClient:
    def __init__(self) -> None:
        self._base_url = settings.TICKET_API_BASE_URL
        self._token = settings.TICKET_API_BEARER_TOKEN

    async def send_message(self, ticket_id: str, text: str) -> bool:
        # AI actor auth (authMode: 'AI') — same Bearer api-token path used by
        # TicketClient for the sibling /ai endpoints, not a human user JWT.
        headers = {"Authorization": f"Bearer {self._token}"}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            try:
                response = await client.post(
                    f"/store-panel/field-service-ticket/{ticket_id}/message/ai",
                    json={"text": text},
                    headers=headers,
                )
            except httpx.HTTPError:
                logger.exception(
                    "Communication log send_message failed for ticket %s", ticket_id
                )
                return False
        return response.status_code == 200
