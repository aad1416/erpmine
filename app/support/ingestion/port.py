"""The ENTIRE contract from app/support/ ingestion into the main service
(02-architecture-decisions.md §9.2).

Plain serializable args/returns (no shared ORM objects) — written as if this were already
a network boundary, since app/support/ is meant to become a separate service later.
process_create_ticket was added when ticket creation became an asynchronous task the
worker claims rather than a call the AI core makes inline. Replies no longer go through
here: the worker hands a send_message task to its Mailbox Adapter, found in the Mailbox
Registry by adapter name.
"""

from __future__ import annotations

import logging

from app.support.adapter.schemas import NormalizedMessage

logger = logging.getLogger(__name__)


async def notify_ai_core(conversation_id: str, messages: list[NormalizedMessage]) -> None:
    """Ingestion → AI core. Called once the ingestion task-processing loop has batched
    all open message tasks for a thread (03-ingestion-service-design.md §4.3) — by this
    point the messages are already fetched/normalized/stored, so this call carries the
    actual batch content, not a bare ping."""
    from app.services.conversation_service import handle_message_batch

    await handle_message_batch(conversation_id=conversation_id, messages=messages)


async def process_create_ticket(
    task_id: str, adapter: str, mailbox: str, conversation_id: str, payload: dict
) -> None:
    """Ingestion → AI core, for a create_ticket task the worker has claimed. The import
    is deferred for the same reason notify_ai_core's is: conversation_service.py imports
    reply_dispatcher.py, which imports this module at load time, so a top-level import
    here would be circular."""
    from app.services.conversation_service import handle_create_ticket_task

    await handle_create_ticket_task(
        task_id=task_id,
        adapter=adapter,
        mailbox=mailbox,
        conversation_id=conversation_id,
        payload=payload,
    )

