"""The message sink: how a Mailbox Adapter hands a normalized message to ingestion.

It writes one `message` task and wakes the ingestion worker. It is idempotent on
(adapter, Mailbox, external message ID), so an adapter that calls it again for the same
message, e.g. after a crash before it recorded the handover, creates no second task. A
message counts as handed over once `message_sink` returns.
"""

import asyncio

from app.db.database import SessionLocal
from app.support.adapter.schemas import NormalizedMessage
from app.support.ingestion.task_repository import TaskRepository
from app.support.ingestion.worker.ingestion_worker import wake_ingestion_worker
from app.support.init import is_support_leader
from app.support.signal_bus import get_signal_bus


async def message_sink(message: NormalizedMessage) -> None:
    db = SessionLocal()
    try:
        task = TaskRepository(db).enqueue_message_task_if_absent(
            mailbox_key=message.mailbox_key,
            conversation_id=message.conversation_id,
            external_message_id=message.external_message_id,
            payload=message.model_dump(mode="json"),
        )
    finally:
        db.close()
    if task is not None:
        wake_ingestion_worker()
        if not is_support_leader():
            # fire and forget
            asyncio.create_task(get_signal_bus().signal_leader())
