"""The ingestion worker's task processing: message batches to the AI core, create_ticket
tasks, and replies through the Mailbox Registry (02-architecture-decisions.md §12.4,
08-unit-test-strategy-checklist.md §5)."""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock

import pytest

from app.config.setting import settings
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.registry import MailboxRegistry
from app.support.adapter.schemas import NormalizedMessage
from app.support.ingestion.models import IngestionTask, TaskStatus
from app.support.ingestion.task_repository import TaskRepository
from app.support.ingestion.worker import ingestion_worker as iw


MAILBOX = MailboxKey("gmail", "s@x.com")


def _message(external_message_id="m1", conversation_id="t1", mailbox_key=MAILBOX):
    return NormalizedMessage(
        adapter=mailbox_key.adapter,
        mailbox=mailbox_key.mailbox,
        conversation_id=conversation_id,
        external_message_id=external_message_id,
        sender_address="a@b.com",
        received_at=datetime.now(UTC),
        body_text="hi there",
    )


class FakeAdapter:
    """Records replies; `fail_for` names Conversations whose send raises."""

    def __init__(self, name, fail_for=()):
        self.name = name
        self.fail_for = set(fail_for)
        self.send_calls = []

    async def send_message(self, mailbox, conversation_id, text, idempotency_key):
        self.send_calls.append((mailbox, conversation_id, text, idempotency_key))
        if conversation_id in self.fail_for:
            raise RuntimeError("smtp down")


def _registry(*adapters) -> MailboxRegistry:
    return MailboxRegistry({adapter.name: adapter for adapter in adapters})


@pytest.mark.asyncio
async def test_process_message_batches_batches_all_open_tasks_per_thread(db_session, monkeypatch):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1",
        payload=_message("m1", "t1").model_dump(mode="json"),
    )
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m2",
        payload=_message("m2", "t1").model_dump(mode="json"),
    )

    notify_mock = AsyncMock()
    monkeypatch.setattr("app.support.ingestion.worker.ingestion_worker.port.notify_ai_core", notify_mock)

    await iw.process_message_batches()

    assert notify_mock.call_count == 1
    conversation_id, messages = notify_mock.call_args.args
    assert conversation_id == "t1"
    assert len(messages) == 2

    tasks = db_session.query(IngestionTask).all()
    assert all(t.status == TaskStatus.done.value for t in tasks)


@pytest.mark.asyncio
async def test_process_message_batches_records_failure_on_notify_error(db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1",
        payload=_message("m1", "t1").model_dump(mode="json"),
    )

    monkeypatch.setattr(
        "app.support.ingestion.worker.ingestion_worker.port.notify_ai_core",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    await iw.process_message_batches()

    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == TaskStatus.open.value  # retried, not dead-lettered yet


@pytest.mark.asyncio
async def test_process_create_ticket_tasks_delegates_to_port_per_task(db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.enqueue(
        task_type="create_ticket", mailbox_key=MAILBOX, conversation_id="t1",
        payload={"unit_serial": "SN123"},
    )

    process_mock = AsyncMock()
    monkeypatch.setattr(
        "app.support.ingestion.worker.ingestion_worker.port.process_create_ticket", process_mock
    )

    await iw.process_create_ticket_tasks()

    process_mock.assert_awaited_once_with(
        task_id=task.id,
        adapter="gmail",
        mailbox="s@x.com",
        conversation_id="t1",
        payload={"unit_serial": "SN123"},
    )
    # The worker doesn't finalize on success — handle_create_ticket_task owns that, and
    # it's mocked out here, so the row is left as the claim left it.
    db_session.expire_all()
    assert db_session.get(IngestionTask, task.id).status == TaskStatus.running.value


@pytest.mark.asyncio
async def test_process_create_ticket_tasks_records_failure_with_reason(db_session, monkeypatch):
    repo = TaskRepository(db_session)
    task = repo.enqueue(
        task_type="create_ticket", mailbox_key=MAILBOX, conversation_id="t1", payload={},
    )

    monkeypatch.setattr(
        "app.support.ingestion.worker.ingestion_worker.port.process_create_ticket",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    await iw.process_create_ticket_tasks()

    db_session.expire_all()
    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == TaskStatus.open.value  # retryable, not dead-lettered yet
    assert stored.payload["last_error"] == "boom"


def _enqueue_send(repo, text, conversation_id="t1", mailbox_key=MAILBOX):
    return repo.enqueue(
        task_type="send_message", mailbox_key=mailbox_key,
        conversation_id=conversation_id, payload={"text": text},
    )


@pytest.mark.asyncio
async def test_process_send_message_tasks_delivers_and_marks_done(db_session):
    repo = TaskRepository(db_session)
    task = _enqueue_send(repo, "hello there")
    gmail = FakeAdapter("gmail")

    await iw.process_send_message_tasks(_registry(gmail))

    # The task ID is the idempotency key.
    assert gmail.send_calls == [("s@x.com", "t1", "hello there", task.id)]
    db_session.expire_all()
    assert db_session.get(IngestionTask, task.id).status == TaskStatus.done.value


@pytest.mark.asyncio
async def test_process_send_message_tasks_records_failure_with_reason(db_session):
    repo = TaskRepository(db_session)
    task = _enqueue_send(repo, "hello there")

    await iw.process_send_message_tasks(_registry(FakeAdapter("gmail", fail_for={"t1"})))

    db_session.expire_all()
    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == TaskStatus.open.value
    assert stored.payload["last_error"] == "smtp down"


@pytest.mark.asyncio
async def test_send_message_failure_halts_remaining_sends_for_that_conversation(db_session):
    """Delivering #2 while #1 is still awaiting retry would reach the customer out of
    order, so a failure stops the rest of that conversation's queue."""
    repo = TaskRepository(db_session)
    first = _enqueue_send(repo, "first")
    second = _enqueue_send(repo, "second")
    gmail = FakeAdapter("gmail", fail_for={"t1"})

    await iw.process_send_message_tasks(_registry(gmail))

    assert len(gmail.send_calls) == 1  # never attempted the second
    db_session.expire_all()
    assert db_session.get(IngestionTask, first.id).status == TaskStatus.open.value
    # Handed back rather than left claimed, and without burning an attempt it never used.
    stranded = db_session.get(IngestionTask, second.id)
    assert stranded.status == TaskStatus.open.value
    assert stranded.attempt_count == 0


@pytest.mark.asyncio
async def test_send_message_failure_does_not_halt_other_conversations(db_session):
    """The ordering guarantee is per conversation — one stuck thread must not block the
    rest of the queue."""
    repo = TaskRepository(db_session)
    _enqueue_send(repo, "for t1", conversation_id="t1")
    other = _enqueue_send(repo, "for t2", conversation_id="t2")

    await iw.process_send_message_tasks(_registry(FakeAdapter("gmail", fail_for={"t1"})))

    db_session.expire_all()
    assert db_session.get(IngestionTask, other.id).status == TaskStatus.done.value


@pytest.mark.asyncio
async def test_reply_reaches_the_adapter_and_mailbox_of_its_task(db_session):
    """Two IMAP Mailboxes and a Gmail one share a conversation_id: each reply goes out
    through its own task's adapter, from its own Mailbox, with nothing parsed."""
    imap = FakeAdapter("imap")
    gmail = FakeAdapter("gmail")

    repo = TaskRepository(db_session)
    to_sales = _enqueue_send(repo, "to sales", mailbox_key=MailboxKey("imap", "sales@shop.com"))
    via_gmail = _enqueue_send(
        repo, "via gmail", mailbox_key=MailboxKey("gmail", "help@shop.com")
    )

    await iw.process_send_message_tasks(_registry(imap, gmail))

    assert imap.send_calls == [("sales@shop.com", "t1", "to sales", to_sales.id)]
    assert gmail.send_calls == [("help@shop.com", "t1", "via gmail", via_gmail.id)]
    db_session.expire_all()
    assert {task.status for task in db_session.query(IngestionTask).all()} == {
        TaskStatus.done.value
    }


@pytest.mark.asyncio
async def test_reply_for_an_unknown_adapter_is_retried_not_marked_sent(db_session):
    """Must fail rather than return: the worker treats a normal return as delivered and
    marks the task done, which would record a reply as sent when no adapter sent it."""
    task = _enqueue_send(
        TaskRepository(db_session), "hello", mailbox_key=MailboxKey("imap", "gone@shop.com")
    )

    await iw.process_send_message_tasks(_registry(FakeAdapter("gmail")))

    db_session.expire_all()
    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == TaskStatus.open.value
    assert "'imap'" in stored.payload["last_error"]
    assert "gone@shop.com" in stored.payload["last_error"]


def test_finished_tasks_are_purged_after_the_retention_period(db_session):
    repo = TaskRepository(db_session)
    old_done = _enqueue_send(repo, "old", conversation_id="t1")
    old_open = _enqueue_send(repo, "old but still open", conversation_id="t2")
    recent_done = _enqueue_send(repo, "recent", conversation_id="t3")
    repo.mark_done(old_done.id)
    repo.mark_done(recent_done.id)
    long_ago = datetime.now(UTC) - timedelta(days=settings.SUPPORT_RETENTION_DAYS + 1)
    db_session.query(IngestionTask).filter(
        IngestionTask.id.in_([old_done.id, old_open.id])
    ).update({"updated_at": long_ago}, synchronize_session=False)
    db_session.commit()

    iw.purge_finished_tasks()

    db_session.expire_all()
    assert {task.id for task in db_session.query(IngestionTask).all()} == {
        old_open.id,
        recent_done.id,
    }
