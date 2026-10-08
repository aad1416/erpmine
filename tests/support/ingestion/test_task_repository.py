"""Task queue hardening (03-ingestion-service-design.md §5-6,
08-unit-test-strategy-checklist.md §4): idempotency, per-conversation locking,
max-retries -> dead-letter, heartbeat reclaim, retention purge."""

from datetime import datetime, timedelta, UTC

from app.support.adapter.mailbox_key import MailboxKey
from app.support.ingestion.models import IngestionTask, TaskStatus
from app.support.ingestion.task_repository import TaskRepository

MAILBOX = MailboxKey("gmail", "s@x.com")
MAILBOX_A = MailboxKey("imap", "a@shop.com")
MAILBOX_B = MailboxKey("imap", "b@shop.com")


def _key(conversation_id, mailbox_key=MAILBOX):
    return (mailbox_key.adapter, mailbox_key.mailbox, conversation_id)


def test_enqueue_message_task_if_absent_is_idempotent(db_session):
    repo = TaskRepository(db_session)
    first = repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    second = repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    assert first is not None
    assert second is None
    assert db_session.query(IngestionTask).count() == 1


def test_claim_open_batches_groups_by_conversation(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={"i": 1}
    )
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m2", payload={"i": 2}
    )
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t2", external_message_id="m3", payload={"i": 3}
    )

    batches = repo.claim_open_batches("message")
    assert set(batches.keys()) == {_key("t1"), _key("t2")}
    assert len(batches[_key("t1")]) == 2
    assert len(batches[_key("t2")]) == 1
    for tasks in batches.values():
        for task in tasks:
            assert task.status == TaskStatus.running.value


def test_claim_open_batches_does_not_merge_across_mailboxes_with_same_conversation_id(db_session):
    """conversation_id is a per-Mailbox thread id, not globally unique — two Mailboxes
    sharing one must not have their tasks batched together (they'd be handed to the AI
    core as a single conversation, misattributing one Mailbox's messages to the other)."""
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX_A, conversation_id="t1", external_message_id="m1", payload={}
    )
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX_B, conversation_id="t1", external_message_id="m2", payload={}
    )

    batches = repo.claim_open_batches("message")
    assert set(batches.keys()) == {_key("t1", MAILBOX_A), _key("t1", MAILBOX_B)}
    assert len(batches[_key("t1", MAILBOX_A)]) == 1
    assert len(batches[_key("t1", MAILBOX_B)]) == 1


def test_per_conversation_lock_is_scoped_by_mailbox(db_session):
    """A running task on one Mailbox must not block a same-conversation_id task on a
    different Mailbox."""
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX_A, conversation_id="t1", external_message_id="m1", payload={}
    )
    repo.claim_open_batches("message")  # _key("t1", MAILBOX_A) now running

    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX_B, conversation_id="t1", external_message_id="m2", payload={}
    )
    second_claim = repo.claim_open_batches("message")
    assert _key("t1", MAILBOX_B) in second_claim


def test_per_conversation_lock_excludes_already_running_conversations(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    repo.claim_open_batches("message")  # t1 now running

    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m2", payload={}
    )
    second_claim = repo.claim_open_batches("message")
    assert _key("t1") not in second_claim


def test_record_failure_retries_until_max_then_dead_letters(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )

    # max_retries=3 means three attempts total: the third failure dead-letters
    # (see 4413daf, which corrected an off-by-one in the threshold).
    statuses = []
    for _ in range(3):
        batch = repo.claim_open_batches("message")
        task = batch[_key("t1")][0]
        statuses.append(repo.record_failure(task.id, max_retries=3))

    assert statuses == [
        TaskStatus.open.value,
        TaskStatus.open.value,
        TaskStatus.dead_letter.value,
    ]
    # Terminal: nothing left to claim.
    assert repo.claim_open_batches("message") == {}


def test_reclaim_stale_resets_stuck_running_tasks_to_open(db_session):
    repo = TaskRepository(db_session)
    task = repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    repo.claim_open_batches("message")

    stored = db_session.get(IngestionTask, task.id)
    stored.heartbeat_at = datetime.now(UTC) - timedelta(seconds=999)
    db_session.commit()

    reclaimed = repo.reclaim_stale(heartbeat_timeout_seconds=120)
    assert reclaimed == 1
    assert db_session.get(IngestionTask, task.id).status == TaskStatus.open.value


def test_reclaim_stale_leaves_fresh_heartbeats_alone(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    repo.claim_open_batches("message")

    reclaimed = repo.reclaim_stale(heartbeat_timeout_seconds=120)
    assert reclaimed == 0


def test_synthesize_dead_letter_is_never_claimable(db_session):
    repo = TaskRepository(db_session)
    task = repo.synthesize_dead_letter(
        task_type="create_ticket",
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"reason": "escalation"},
    )
    assert task.status == TaskStatus.dead_letter.value
    assert repo.claim_open_batches("create_ticket") == {}


def test_mark_dead_letter_finalizes_the_existing_row_without_spawning_another(db_session):
    repo = TaskRepository(db_session)
    task = repo.enqueue(
        task_type="create_ticket", mailbox_key=MAILBOX, conversation_id="t1",
        payload={"unit_serial": "SN123"},
    )

    repo.mark_dead_letter(task.id, payload_patch={"reason": "STORE_NOT_FOUND"})

    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == TaskStatus.dead_letter.value
    assert stored.payload["reason"] == "STORE_NOT_FOUND"
    assert stored.payload["unit_serial"] == "SN123"  # patch merges, doesn't replace
    assert db_session.query(IngestionTask).count() == 1


def test_mark_dead_letter_is_a_noop_for_unknown_task_id(db_session):
    TaskRepository(db_session).mark_dead_letter("no-such-task", payload_patch={"reason": "x"})
    assert db_session.query(IngestionTask).count() == 0


def test_release_unattempted_returns_claimed_tasks_without_burning_an_attempt(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    task = repo.claim_open_batches("message")[_key("t1")][0]
    assert task.attempt_count == 1

    repo.release_unattempted([task.id])

    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == TaskStatus.open.value
    assert stored.attempt_count == 0


def test_release_unattempted_ignores_tasks_that_are_not_running(db_session):
    repo = TaskRepository(db_session)
    task = repo.enqueue(
        task_type="message", mailbox_key=MAILBOX, conversation_id="t1", payload={},
        status=TaskStatus.done.value, external_message_id="m1",
    )

    repo.release_unattempted([task.id])

    assert db_session.get(IngestionTask, task.id).status == TaskStatus.done.value


def test_record_failure_records_last_error_while_still_retryable(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={"i": 1}
    )
    task = repo.claim_open_batches("message")[_key("t1")][0]

    assert repo.record_failure(task.id, max_retries=3, error_detail="boom") == TaskStatus.open.value

    stored = db_session.get(IngestionTask, task.id)
    assert stored.payload["last_error"] == "boom"
    assert stored.payload["i"] == 1  # original payload preserved


def test_record_failure_records_last_error_on_final_dead_letter(db_session):
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    for _ in range(2):
        task = repo.claim_open_batches("message")[_key("t1")][0]
        repo.record_failure(task.id, max_retries=3, error_detail="transient")

    task = repo.claim_open_batches("message")[_key("t1")][0]
    assert (
        repo.record_failure(task.id, max_retries=3, error_detail="final failure")
        == TaskStatus.dead_letter.value
    )
    assert db_session.get(IngestionTask, task.id).payload["last_error"] == "final failure"


def test_record_failure_leaves_payload_untouched_without_error_detail(db_session):
    """The message-task call site doesn't pass error_detail and must be unaffected."""
    repo = TaskRepository(db_session)
    repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={"i": 1}
    )
    task = repo.claim_open_batches("message")[_key("t1")][0]

    repo.record_failure(task.id, max_retries=3)

    assert db_session.get(IngestionTask, task.id).payload == {"i": 1}


def test_purge_terminal_older_than_retention_window(db_session):
    repo = TaskRepository(db_session)
    task = repo.enqueue(
        task_type="message", mailbox_key=MAILBOX, conversation_id="t1", payload={},
        status=TaskStatus.done.value, external_message_id="m1",
    )
    stored = db_session.get(IngestionTask, task.id)
    stored.updated_at = datetime.now(UTC) - timedelta(days=8)
    db_session.commit()

    assert repo.purge_terminal_older_than(retention_days=7) == 1
    assert db_session.query(IngestionTask).count() == 0


def test_open_and_running_tasks_are_never_purged(db_session):
    repo = TaskRepository(db_session)
    task = repo.enqueue_message_task_if_absent(
        mailbox_key=MAILBOX, conversation_id="t1", external_message_id="m1", payload={}
    )
    stored = db_session.get(IngestionTask, task.id)
    stored.updated_at = datetime.now(UTC) - timedelta(days=30)
    db_session.commit()

    assert repo.purge_terminal_older_than(retention_days=7) == 0
    assert db_session.query(IngestionTask).count() == 1
