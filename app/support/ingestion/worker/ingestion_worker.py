"""The ingestion worker: claims the tasks the message sink and the AI core queue, per
Conversation, and runs them (§5, §9.1).

Three task types are processed asynchronously through this queue, in this order within a
single locked pass, so work queued by one step is picked up by a later step in the same
pass rather than waiting for the next one:

1. `message` — inbound messages, batched per thread and handed to the AI core.
2. `create_ticket` — enqueued when the decision agent picks that tool; executed via
   `port.process_create_ticket`, which calls the ticket API and resolves the outcome.
3. `send_message` — every outbound customer-facing message, from any of the three tools
   and from escalation; executed by the task's Mailbox Adapter, looked up in the Mailbox
   Registry by the task's adapter name.

Both 2 and 3 exist so the external call each performs has its own attempt counter and
dead-letter state. Previously each ran inline inside the conversation turn, which meant a
transient failure could only be retried by retrying the whole message turn — re-invoking
the LLM, which might decide differently — and a send that failed after a ticket had
already been created could not be retried at all, because the conversation's ticket_id was
by then set and the retry would no-op.

**Revised** — `02-architecture-decisions.md` §7.2/§9.2 and `03-ingestion-service-design.md`
§3-4 previously described create_ticket as a direct call/response cycle, outbound dispatch
as synchronous, and `port.py` as exposing exactly two functions. Doc 03's original
"create ticket task" type turned out to be the right model after all. Those sections carry
superseding notes.

Still synchronous, within the conversation turn: the `ask_question` and `reply` tool calls
themselves — but only their bookkeeping, since their outgoing text is queued as a
`send_message` task like everything else. `TaskType.ask_question` exists only for the
synthesized, already-dead-lettered escalation marker rows `conversation_service.py` creates
for audit purposes (§10.1) — this worker never claims those, since it only claims
`status='open'` rows and they are created directly in `dead_letter` status.

`IngestionWorker` runs these task passes in its own loop, woken by `wake_ingestion_worker`
when the message sink writes a task, with a fallback interval for everything else. The
same loop purges finished tasks older than SUPPORT_RETENTION_DAYS once a day.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.config.setting import settings
from app.db.database import SessionLocal
from app.services.seed_scheduler import seed_file_lock
from app.support.adapter.registry import MailboxRegistry
from app.support.adapter.schemas import NormalizedMessage
from app.support.ingestion import port
from app.support.ingestion.models import TaskType
from app.support.ingestion.task_repository import TaskRepository

logger = logging.getLogger(__name__)

_TASK_PURGE_INTERVAL_SECONDS = 24 * 60 * 60


async def run_task_pass(mailbox_registry: MailboxRegistry) -> None:
    """One pass of the worker loop: reclaim stale tasks, then process every open task.
    Adapters hand messages over through the sink, so nothing is fetched here."""
    with seed_file_lock(settings.SUPPORT_LOCK_FILE) as acquired:
        if not acquired:
            logger.info("Task pass skipped — another pass holds the lock")
            return
        _reclaim_stale()
        await _process_tasks(mailbox_registry)


async def _process_tasks(mailbox_registry: MailboxRegistry) -> None:
    await process_message_batches()
    # After message processing, so a create_ticket task enqueued by a turn in this
    # same pass is claimable (its message task is 'done' by now, not 'running') and
    # gets resolved before the pass releases the lock.
    await process_create_ticket_tasks()
    # Last, so replies queued by either of the two steps above go out before the
    # pass releases the lock.
    await process_send_message_tasks(mailbox_registry)


def _reclaim_stale() -> None:
    db = SessionLocal()
    try:
        reclaimed = TaskRepository(db).reclaim_stale(
            settings.SUPPORT_TASK_HEARTBEAT_TIMEOUT_SECONDS
        )
        if reclaimed:
            logger.info("Reclaimed %d stale ingestion task(s)", reclaimed)
    finally:
        db.close()


async def process_message_batches(max_conversations: int = 10) -> None:
    db = SessionLocal()
    try:
        batches = TaskRepository(db).claim_open_batches(
            TaskType.message.value, max_conversations=max_conversations
        )
    finally:
        db.close()

    for (_adapter, _mailbox, conversation_id), tasks in batches.items():
        await _process_one_batch(conversation_id, tasks)


async def _process_one_batch(conversation_id: str, tasks: list) -> None:
    messages = [NormalizedMessage.model_validate(task.payload) for task in tasks]
    task_ids = [task.id for task in tasks]

    db = SessionLocal()
    try:
        TaskRepository(db).refresh_heartbeat(task_ids)
    finally:
        db.close()

    try:
        await port.notify_ai_core(conversation_id, messages)
    except Exception:
        logger.exception("notify_ai_core failed for conversation_id=%s", conversation_id)
        db = SessionLocal()
        try:
            task_repo = TaskRepository(db)
            for task_id in task_ids:
                task_repo.record_failure(task_id, settings.SUPPORT_TASK_MAX_RETRIES)
        finally:
            db.close()
        return

    db = SessionLocal()
    try:
        task_repo = TaskRepository(db)
        for task_id in task_ids:
            task_repo.mark_done(task_id)
    finally:
        db.close()


async def process_create_ticket_tasks(max_conversations: int = 10) -> None:
    db = SessionLocal()
    try:
        batches = TaskRepository(db).claim_open_batches(
            TaskType.create_ticket.value, max_conversations=max_conversations
        )
    finally:
        db.close()

    for (_adapter, _mailbox, conversation_id), tasks in batches.items():
        for task in tasks:
            await _process_one_create_ticket_task(conversation_id, task)


async def _process_one_create_ticket_task(conversation_id: str, task) -> None:
    """No mark_done on the success path: handle_create_ticket_task decides the terminal
    status itself (done, or dead_letter for outcomes a retry can't change)."""
    db = SessionLocal()
    try:
        TaskRepository(db).refresh_heartbeat([task.id])
    finally:
        db.close()

    try:
        await port.process_create_ticket(
            task_id=task.id,
            adapter=task.adapter,
            mailbox=task.mailbox,
            conversation_id=conversation_id,
            payload=task.payload,
        )
    except Exception as exc:
        logger.exception("process_create_ticket failed for conversation_id=%s", conversation_id)
        db = SessionLocal()
        try:
            TaskRepository(db).record_failure(
                task.id, settings.SUPPORT_TASK_MAX_RETRIES, error_detail=str(exc)
            )
        finally:
            db.close()


async def process_send_message_tasks(
    mailbox_registry: MailboxRegistry, max_conversations: int = 10
) -> None:
    db = SessionLocal()
    try:
        batches = TaskRepository(db).claim_open_batches(
            TaskType.send_message.value, max_conversations=max_conversations
        )
    finally:
        db.close()

    for (_adapter, _mailbox, conversation_id), tasks in batches.items():
        for index, task in enumerate(tasks):
            if await _process_one_send_message_task(conversation_id, task, mailbox_registry):
                continue
            # Tasks are ordered by created_at; sending a later one while an earlier one
            # is still awaiting retry would reach the customer out of order. Only this
            # conversation stops — the rest are independent — and the tasks behind it go
            # back to 'open' rather than sitting claimed until the heartbeat timeout.
            db = SessionLocal()
            try:
                TaskRepository(db).release_unattempted(
                    [t.id for t in tasks[index + 1 :]]
                )
            finally:
                db.close()
            break


async def _process_one_send_message_task(
    conversation_id: str, task, mailbox_registry: MailboxRegistry
) -> bool:
    db = SessionLocal()
    try:
        TaskRepository(db).refresh_heartbeat([task.id])
    finally:
        db.close()

    try:
        await _send_reply(task, conversation_id, mailbox_registry)
    except Exception as exc:
        logger.exception("send_message failed for conversation_id=%s", conversation_id)
        db = SessionLocal()
        try:
            TaskRepository(db).record_failure(
                task.id, settings.SUPPORT_TASK_MAX_RETRIES, error_detail=str(exc)
            )
        finally:
            db.close()
        return False

    db = SessionLocal()
    try:
        TaskRepository(db).mark_done(task.id)
    finally:
        db.close()
    return True


async def _send_reply(task, conversation_id: str, mailbox_registry: MailboxRegistry) -> None:
    """The task ID is the idempotency key, so a retried task can't send twice.

    Raises rather than skipping when no adapter has the task's name: the caller marks a
    task done on a normal return, which would record a reply as sent when nothing was.
    Raising routes it through retry and dead-letter, so the mistake stays visible."""
    mailbox_adapter = mailbox_registry.get(task.adapter)
    if mailbox_adapter is None:
        raise LookupError(
            f"send_message: no Mailbox Adapter named {task.adapter!r} "
            f"(mailbox={task.mailbox!r})"
        )
    await mailbox_adapter.send_message(
        task.mailbox, conversation_id, task.payload["text"], idempotency_key=task.id
    )


def purge_finished_tasks() -> None:
    """Deletes done and dead-lettered tasks older than SUPPORT_RETENTION_DAYS. Open and
    running tasks are never purged, whatever their age."""
    db = SessionLocal()
    try:
        deleted = TaskRepository(db).purge_terminal_older_than(settings.SUPPORT_RETENTION_DAYS)
        if deleted:
            logger.info("Purged %d finished ingestion task(s)", deleted)
    finally:
        db.close()


class IngestionWorker:
    """Runs task passes in its own loop: at once when woken, otherwise every
    `fallback_interval_seconds` so tasks nobody woke it for (a reclaimed or retried
    task, a reply queued outside a pass) still run. Purges finished tasks on its first
    pass and then once a day."""

    def __init__(
        self,
        mailbox_registry: MailboxRegistry,
        fallback_interval_seconds: float,
        signal_bus=None):

        self.mailbox_registry = mailbox_registry
        self._fallback_interval_seconds = fallback_interval_seconds
        self._signal_bus = signal_bus
        self._wake_event = asyncio.Event()
        self._loop_task: asyncio.Task | None = None
        self._listener_task: asyncio.Task | None = None
        self._last_purge_at: float | None = None

    def start(self) -> None:
        global _running_worker
        if _running_worker is not None:
            raise RuntimeError("an ingestion worker is already running")
        _running_worker = self
        self._loop_task = asyncio.create_task(self._run(), name="support-ingestion-worker")
        if self._signal_bus is not None:
            self._listener_task = asyncio.create_task(self._listen_signals(), name="support-signal-listener")
        logger.info(
            "Ingestion worker started (fallback interval=%ss)", self._fallback_interval_seconds
        )

    async def stop(self) -> None:
        """Cancels a pass in progress: its claimed tasks are reclaimed by heartbeat
        timeout on the next start, as after a crash."""
        global _running_worker
        if _running_worker is self:
            _running_worker = None

        for task in (self._listener_task, self._loop_task):   # listener first
            if task is None:
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._listener_task = None
        self._loop_task = None
        logger.info("Ingestion worker stopped")

    def wake(self) -> None:
        self._wake_event.set()

    async def _listen_signals(self) -> None:
        """bridge Redis signals to the in-process wake event (leader only)"""
        while True:
            await self._signal_bus.wait_for_signal(
                timeout=self._fallback_interval_seconds
            )
            self._wake_event.set()

    async def _purge_finished_tasks_if_due(self) -> None:
        now = time.monotonic()
        if (
            self._last_purge_at is not None
            and now - self._last_purge_at < _TASK_PURGE_INTERVAL_SECONDS
        ):
            return
        self._last_purge_at = now
        try:
            await asyncio.to_thread(purge_finished_tasks)
        except Exception:
            logger.exception("Purging finished ingestion tasks failed")

    async def _run(self) -> None:
        while True:
            # Cleared before the pass, so a wake arriving during it runs another pass.
            self._wake_event.clear()
            try:
                await run_task_pass(self.mailbox_registry)
            except Exception:
                logger.exception("Ingestion task pass failed")
            await self._purge_finished_tasks_if_due()
            try:
                await asyncio.wait_for(
                    self._wake_event.wait(), timeout=self._fallback_interval_seconds
                )
            except TimeoutError:
                pass


_running_worker: IngestionWorker | None = None


def wake_ingestion_worker() -> None:
    """Called by the message sink after it writes a task. A no-op when no worker runs."""
    if _running_worker is not None:
        _running_worker.wake()

