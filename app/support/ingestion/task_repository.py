"""Database-backed task queue repository (03-ingestion-service-design.md §3, §5-6).

Claims work via a plain UPDATE ... WHERE status='open' rather than
`SELECT ... FOR UPDATE SKIP LOCKED` — this repo runs against SQLite today (single writer
lock, no row-level locking) but the UPDATE-based claim is equally correct on Postgres, so
it ports with no code change if/when the app moves off SQLite. A single worker instance is
assumed; the per-conversation lock below is enforced by query, not a DB-level lock.
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.support.adapter.mailbox_key import MailboxKey
from app.support.ingestion.models import IngestionTask, TaskStatus, TaskType

# (adapter, mailbox, conversation_id): a Conversation's natural key. conversation_id alone
# is a per-Mailbox thread id and isn't globally unique.
ConversationKey = tuple[str, str, str]


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def enqueue(
        self,
        *,
        task_type: str,
        mailbox_key: MailboxKey,
        conversation_id: str,
        payload: dict,
        idempotency_key: str | None = None,
        status: str = TaskStatus.open.value,
        external_message_id: str | None = None,
        commit: bool = True,
    ) -> IngestionTask:
        """`commit=False` defers to a caller-owned transaction, so the task row lands
        atomically with whatever state made it necessary."""
        task = IngestionTask(
            task_type=task_type,
            adapter=mailbox_key.adapter,
            mailbox=mailbox_key.mailbox,
            conversation_id=conversation_id,
            payload=payload,
            idempotency_key=idempotency_key,
            status=status,
            external_message_id=external_message_id,
        )
        self.db.add(task)
        if commit:
            self.db.commit()
            self.db.refresh(task)
        return task

    def enqueue_message_task_if_absent(
        self,
        *,
        mailbox_key: MailboxKey,
        conversation_id: str,
        external_message_id: str,
        payload: dict,
    ) -> IngestionTask | None:
        """Idempotent on (task_type='message', adapter, mailbox, external_message_id) —
        an adapter may hand the same message to the sink again (e.g. re-sinking an
        outbox row after a crash); this must not create a second task for it."""
        task = IngestionTask(
            task_type=TaskType.message.value,
            adapter=mailbox_key.adapter,
            mailbox=mailbox_key.mailbox,
            conversation_id=conversation_id,
            payload=payload,
            external_message_id=external_message_id,
        )
        self.db.add(task)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return None
        self.db.refresh(task)
        return task

    def synthesize_dead_letter(
        self,
        *,
        task_type: str,
        mailbox_key: MailboxKey,
        conversation_id: str,
        payload: dict,
        idempotency_key: str | None = None,
    ) -> IngestionTask:
        """A queryable, never-executed row — status is dead_letter from creation, and
        the worker never picks it up (it only claims status='open' rows). Used for
        escalations that never got as far as a real create_ticket attempt (see
        conversation_service.py's escalation handling)."""
        return self.enqueue(
            task_type=task_type,
            mailbox_key=mailbox_key,
            conversation_id=conversation_id,
            payload=payload,
            idempotency_key=idempotency_key,
            status=TaskStatus.dead_letter.value,
        )

    def has_open_or_running(
        self, task_type: str, mailbox_key: MailboxKey, conversation_id: str
    ) -> bool:
        """Guards create_ticket enqueues, which — unlike message tasks — have no
        external_message_id to dedupe on (NULL is exempt from
        uq_ingestion_task_adapter_mailbox_dedup).
        A crash between the enqueue and the triggering message task's mark_done would
        otherwise re-run the turn and enqueue a second ticket-creation task."""
        return (
            self.db.query(IngestionTask.id)
            .filter(
                IngestionTask.task_type == task_type,
                IngestionTask.adapter == mailbox_key.adapter,
                IngestionTask.mailbox == mailbox_key.mailbox,
                IngestionTask.conversation_id == conversation_id,
                IngestionTask.status.in_(
                    [TaskStatus.open.value, TaskStatus.running.value]
                ),
            )
            .first()
            is not None
        )

    def list_for_conversation(
        self, mailbox_key: MailboxKey, conversation_id: str
    ) -> list[IngestionTask]:
        """Read-only, for the monitoring API's thread detail view — every task ever
        enqueued for this thread (subject to the same retention purge as everything
        else), not just claimable ones."""
        return (
            self.db.query(IngestionTask)
            .filter(
                IngestionTask.adapter == mailbox_key.adapter,
                IngestionTask.mailbox == mailbox_key.mailbox,
                IngestionTask.conversation_id == conversation_id,
            )
            .order_by(IngestionTask.created_at.asc())
            .all()
        )

    def list_for_conversations(
        self, keys: list[ConversationKey]
    ) -> list[IngestionTask]:
        """Batch form of list_for_conversation, for the monitoring API's thread list
        view — avoids one query per thread."""
        if not keys:
            return []
        conditions = [
            and_(
                IngestionTask.adapter == adapter,
                IngestionTask.mailbox == mailbox,
                IngestionTask.conversation_id == conversation_id,
            )
            for adapter, mailbox, conversation_id in keys
        ]
        return (
            self.db.query(IngestionTask)
            .filter(or_(*conditions))
            .order_by(IngestionTask.created_at.asc())
            .all()
        )

    def _running_conversation_keys(self) -> set[ConversationKey]:
        rows = (
            self.db.query(
                IngestionTask.adapter, IngestionTask.mailbox, IngestionTask.conversation_id
            )
            .filter(IngestionTask.status == TaskStatus.running.value)
            .distinct()
            .all()
        )
        return {(adapter, mailbox, conversation_id) for adapter, mailbox, conversation_id in rows}

    def claim_open_batches(
        self, task_type: str, max_conversations: int = 10
    ) -> dict[ConversationKey, list[IngestionTask]]:
        """Claims all open tasks of `task_type`, grouped by (adapter, mailbox,
        conversation_id), for up to `max_conversations` conversations that don't already
        have a task 'running' (per-conversation lock, §5 hardening #4). Scoped by Mailbox
        as well as conversation because conversation_id alone is a per-Mailbox thread id
        and isn't globally unique — Conversation's own uniqueness is (adapter, mailbox,
        conversation_id) — so keying on it alone could merge two Mailboxes' tasks into
        one batch, or let one Mailbox's running task block another's. Message tasks
        are batched per-thread this way (§4.3) — every open task for a claimed
        conversation comes back together, not one at a time."""
        running = self._running_conversation_keys()
        open_tasks = (
            self.db.query(IngestionTask)
            .filter(
                IngestionTask.task_type == task_type,
                IngestionTask.status == TaskStatus.open.value,
            )
            .order_by(IngestionTask.created_at.asc())
            .all()
        )
        if running:
            # Composite-key membership, so this is a Python-side filter rather than a
            # SQL `NOT IN` — open_tasks is materialized either way.
            open_tasks = [task for task in open_tasks if _conversation_key(task) not in running]

        by_conversation: dict[ConversationKey, list[IngestionTask]] = {}
        for task in open_tasks:
            by_conversation.setdefault(_conversation_key(task), []).append(task)

        picked = dict(list(by_conversation.items())[:max_conversations])
        candidate_ids = [task.id for tasks in picked.values() for task in tasks]
        if not candidate_ids:
            return {}

        now = datetime.now(UTC)
        self.db.query(IngestionTask).filter(
            IngestionTask.id.in_(candidate_ids),
            IngestionTask.status == TaskStatus.open.value,
        ).update(
            {
                "status": TaskStatus.running.value,
                "heartbeat_at": now,
                "attempt_count": IngestionTask.attempt_count + 1,
            },
            synchronize_session=False,
        )
        self.db.commit()
        for tasks in picked.values():
            for task in tasks:
                self.db.refresh(task)
        return picked

    def refresh_heartbeat(self, task_ids: list[str]) -> None:
        if not task_ids:
            return
        self.db.query(IngestionTask).filter(
            IngestionTask.id.in_(task_ids),
            IngestionTask.status == TaskStatus.running.value,
        ).update({"heartbeat_at": datetime.now(UTC)}, synchronize_session=False)
        self.db.commit()

    def mark_done(self, task_id: str, commit: bool = True) -> None:
        task = self.db.get(IngestionTask, task_id)
        if task is not None:
            task.status = TaskStatus.done.value
            if commit:
                self.db.commit()

    def mark_dead_letter(
        self, task_id: str, payload_patch: dict | None = None, commit: bool = True
    ) -> None:
        """Finalizes an already-claimed task as dead_letter in place, for outcomes that
        are definitive and non-retryable (retrying cannot change the answer). Distinct
        from synthesize_dead_letter, which creates a fresh audit row for escalations that
        never had a claimed task to finalize."""
        task = self.db.get(IngestionTask, task_id)
        if task is None:
            return
        task.status = TaskStatus.dead_letter.value
        if payload_patch:
            task.payload = {**task.payload, **payload_patch}
        if commit:
            self.db.commit()

    def record_failure(
        self, task_id: str, max_retries: int, error_detail: str | None = None
    ) -> str:
        """§6 item 4: once attempt_count exceeds max_retries, dead-letter instead of
        retrying again. Otherwise the task goes back to 'open' for the next pass.

        `error_detail` is merged into the payload as `last_error` on every failed
        attempt, not just the final one, so a still-retrying task shows why it is
        currently failing rather than only why it eventually gave up. Callers that omit
        it leave the payload untouched."""
        task = self.db.get(IngestionTask, task_id)
        if task is None:
            return TaskStatus.dead_letter.value
        if error_detail:
            task.payload = {**task.payload, "last_error": error_detail}
        if task.attempt_count >= max_retries:
            task.status = TaskStatus.dead_letter.value
        else:
            task.status = TaskStatus.open.value
        self.db.commit()
        return task.status

    def release_unattempted(self, task_ids: list[str]) -> None:
        """Returns claimed-but-never-attempted tasks to 'open'. claim_open_batches takes a
        whole conversation at once and increments attempt_count up front, so a caller that
        stops partway through a batch (send_message halts on the first failure to preserve
        ordering) must hand the rest back — otherwise they sit 'running' until the
        heartbeat timeout and lose an attempt they never used."""
        if not task_ids:
            return
        self.db.query(IngestionTask).filter(
            IngestionTask.id.in_(task_ids),
            IngestionTask.status == TaskStatus.running.value,
        ).update(
            {
                "status": TaskStatus.open.value,
                "attempt_count": IngestionTask.attempt_count - 1,
            },
            synchronize_session=False,
        )
        self.db.commit()

    def reclaim_stale(self, heartbeat_timeout_seconds: int) -> int:
        """§5 hardening #2: a task whose heartbeat hasn't moved within the timeout is
        assumed crashed and is reset to 'open' so another pass can retry it."""
        cutoff = datetime.now(UTC) - timedelta(seconds=heartbeat_timeout_seconds)
        count = (
            self.db.query(IngestionTask)
            .filter(
                IngestionTask.status == TaskStatus.running.value,
                IngestionTask.heartbeat_at < cutoff,
            )
            .update({"status": TaskStatus.open.value}, synchronize_session=False)
        )
        self.db.commit()
        return count

    def purge_terminal_older_than(self, retention_days: int) -> int:
        """SUPPORT_RETENTION_DAYS retention for task rows (05-decisions-checklist.md),
        including escalation-caused dead-letters."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        deleted = (
            self.db.query(IngestionTask)
            .filter(
                IngestionTask.status.in_(
                    [TaskStatus.done.value, TaskStatus.dead_letter.value]
                ),
                IngestionTask.updated_at < cutoff,
            )
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted


def _conversation_key(task: IngestionTask) -> ConversationKey:
    return (task.adapter, task.mailbox, task.conversation_id)
