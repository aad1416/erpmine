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
    if not unsynced:
        if commit:
            db.commit()
        return
    existing_ids = {
        message_id
        for (message_id,) in db.query(PendingLogSync.conversation_message_id)
        .filter(
            PendingLogSync.conversation_message_id.in_(
                [message.id for message in unsynced]
            )
        )
        .all()
    }
    for message in unsynced:
        if message.id not in existing_ids:
            db.add(PendingLogSync(ticket_id=ticket_id, conversation_message_id=message.id))
    if commit:
        db.commit()


class CommunicationLogClient:
    def __init__(self) -> None:
        self._base_url = settings.TICKET_API_BASE_URL
        self._token = settings.TICKET_API_BEARER_TOKEN

    async def send_message(
        self,
        ticket_id: str,
        text: str,
        *,
        idempotency_key: str,
        is_sender_the_client: bool,
    ) -> bool:
        # AI actor auth (authMode: 'AI') — same Bearer api-token path used by
        # TicketClient for the sibling /ai endpoints, not a human user JWT.
        headers = {
            "Authorization": f"Bearer {self._token}",
            "x-id": idempotency_key,
        }
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            try:
                response = await client.post(
                    f"/store-panel/field-service-ticket/{ticket_id}/message/ai",
                    json={"text": text, "isSenderTheClient": is_sender_the_client},
                    headers=headers,
                )
            except httpx.HTTPError:
                logger.exception(
                    "Communication log send_message failed for ticket %s", ticket_id
                )
                return False
        if response.status_code != 200:
            logger.warning(
                "Communication log API rejected ticket %s message %s: HTTP %s, response %s",
                ticket_id,
                idempotency_key,
                response.status_code,
                response.text[:500],
            )
        return response.status_code == 200
