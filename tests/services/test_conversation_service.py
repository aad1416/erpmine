"""Decision-agent orchestration and lifecycle edges (02-architecture-decisions.md §10,
08-unit-test-strategy-checklist.md §2, §8)."""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

import pytest

import app.services.conversation_service as cs
from app.db.models.Conversation import Conversation
from app.db.models.PendingLogSync import PendingLogSync
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage
from app.support.ingestion.models import IngestionTask
from app.support.ingestion.task_repository import TaskRepository


MAILBOX = MailboxKey("gmail", "support@acme.com")


def _message(conversation_id="thread1", text="Hi, my unit broke"):
    return NormalizedMessage(
        adapter=MAILBOX.adapter,
        mailbox=MAILBOX.mailbox,
        conversation_id=conversation_id,
        external_message_id="m1",
        sender_address="cust@x.com",
        received_at=datetime.now(UTC),
        body_text=text,
    )


_TICKET_ARGS = {
    "unit_serial": "SN123",
    "issue_description": "broken",
    "title": "Broken unit",
    "customer_message": "Ticket created!",
}


def _queued_replies(db_session, conversation_id="thread1"):
    """Outbound text is no longer dispatched inline — it's queued as a send_message task
    for the worker, so assertions read the queue rather than a dispatch mock."""
    db_session.expire_all()
    return [
        task.payload["text"]
        for task in db_session.query(IngestionTask)
        .filter_by(task_type="send_message", conversation_id=conversation_id)
        .order_by(IngestionTask.created_at.asc())
        .all()
    ]


def _enqueue_create_ticket_task(db_session, conversation_id="thread1"):
    """handle_create_ticket_task finalizes a real claimed row, so tests need one."""
    return TaskRepository(db_session).enqueue(
        task_type="create_ticket",
        mailbox_key=MAILBOX,
        conversation_id=conversation_id,
        payload=_TICKET_ARGS,
    )


def _seed_conversation(db_session, **fields):
    conversation = Conversation(
        adapter=MAILBOX.adapter,
        mailbox=MAILBOX.mailbox,
        conversation_id="thread1",
        **fields,
    )
    db_session.add(conversation)
    db_session.commit()
    return conversation


def _fake_decision_agent(tool_called: str, **ctx_fields):
    async def _run(self, *, run_input, ctx, allow_gathering_tools):
        _fake_decision_agent.last_allow_gathering_tools = allow_gathering_tools
        ctx.tool_called = tool_called
        for key, value in ctx_fields.items():
            setattr(ctx, key, value)
        return ctx

    return _run


@pytest.mark.asyncio
async def test_reply_tool_dispatches_text_and_logs_message(db_session):
    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent("reply", reply_text="You're welcome!"),
    ):
        await cs.handle_message_batch("thread1", [_message()])

    assert _queued_replies(db_session) == ["You're welcome!"]


@pytest.mark.asyncio
async def test_ask_question_baseline_increments_question_round_count(db_session):
    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent(
            "ask_question", ask_question_text="What's the serial?", ask_question_reason="baseline"
        ),
    ):
        await cs.handle_message_batch("thread1", [_message()])

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.question_round_count == 1
    assert conversation.serial_correction_attempt_count == 0


@pytest.mark.asyncio
async def test_ask_question_serial_correction_increments_separate_counter(db_session):
    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent(
            "ask_question", ask_question_text="Please recheck the serial", ask_question_reason="serial_correction"
        ),
    ):
        await cs.handle_message_batch("thread1", [_message()])

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.question_round_count == 0
    assert conversation.serial_correction_attempt_count == 1


# --- handle_message_batch side: a create_ticket tool call only enqueues a task ---


@pytest.mark.asyncio
async def test_create_ticket_tool_call_enqueues_task_without_calling_the_api(db_session):
    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent("create_ticket", create_ticket_args=_TICKET_ARGS),
    ), patch(
        "app.services.ticket_client.TicketClient.create_ticket", new=AsyncMock()
    ) as mock_api:
        await cs.handle_message_batch("thread1", [_message()])

    assert mock_api.await_count == 0
    assert _queued_replies(db_session) == []

    task = db_session.query(IngestionTask).filter_by(task_type="create_ticket").one()
    assert task.status == "open"
    assert (task.adapter, task.mailbox) == ("gmail", "support@acme.com")
    assert task.conversation_id == "thread1"
    assert task.payload == _TICKET_ARGS

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.ticket_id is None


@pytest.mark.asyncio
async def test_create_ticket_does_not_enqueue_a_second_task_while_one_is_in_flight(db_session):
    """A crash between the enqueue and the message task's mark_done re-runs the turn;
    the in-flight guard is what stops that producing a second ticket."""
    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent("create_ticket", create_ticket_args=_TICKET_ARGS),
    ):
        await cs.handle_message_batch("thread1", [_message()])
        await cs.handle_message_batch("thread1", [_message(text="resent")])

    assert db_session.query(IngestionTask).filter_by(task_type="create_ticket").count() == 1


# --- worker side: handle_create_ticket_task resolves the outcome ---


@pytest.mark.asyncio
async def test_create_ticket_success_sets_ticket_id_and_enqueues_backfill(db_session):
    task = _enqueue_create_ticket_task(db_session)
    outcome = cs.TicketOutcome(kind="created", ticket_id="tk-1", ticket_number="FS-100")

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=outcome),
    ):
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="gmail",
            mailbox="support@acme.com",
            conversation_id="thread1",
            payload=_TICKET_ARGS,
        )

    # handle_create_ticket_task commits on its own session; drop this session's
    # identity-map copies so assertions read committed state.
    db_session.expire_all()

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.ticket_id == "tk-1"
    assert conversation.unit_serial == "SN123"
    assert _queued_replies(db_session) == ["Ticket created!"]
    assert db_session.query(PendingLogSync).filter_by(ticket_id="tk-1").count() >= 1
    assert db_session.get(IngestionTask, task.id).status == "done"


@pytest.mark.asyncio
async def test_create_ticket_duplicate_overrides_model_text_with_deterministic_message(db_session):
    task = _enqueue_create_ticket_task(db_session)
    outcome = cs.TicketOutcome(
        kind="duplicate", existing_ticket={"id": "tk-existing", "number": "FS-50", "status": "IN_PROGRESS"}
    )

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=outcome),
    ):
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="gmail",
            mailbox="support@acme.com",
            conversation_id="thread1",
            payload={**_TICKET_ARGS, "customer_message": "this text was composed blind"},
        )

    # handle_create_ticket_task commits on its own session; drop this session's
    # identity-map copies so assertions read committed state.
    db_session.expire_all()

    (dispatched_text,) = _queued_replies(db_session)
    assert "FS-50" in dispatched_text
    assert "IN_PROGRESS" in dispatched_text
    assert "composed blind" not in dispatched_text

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.ticket_id == "tk-existing"
    assert db_session.get(IngestionTask, task.id).status == "done"


@pytest.mark.asyncio
async def test_create_ticket_duplicate_without_id_dead_letters_the_claimed_task(db_session):
    task = _enqueue_create_ticket_task(db_session)
    outcome = cs.TicketOutcome(
        kind="duplicate", existing_ticket={"number": "FS-50", "status": "IN_PROGRESS"}
    )

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=outcome),
    ):
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="gmail",
            mailbox="support@acme.com",
            conversation_id="thread1",
            payload=_TICKET_ARGS,
        )

    # handle_create_ticket_task commits on its own session; drop this session's
    # identity-map copies so assertions read committed state.
    db_session.expire_all()

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.ticket_id is None

    # The claimed row itself is finalized — no second audit row alongside it.
    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == "dead_letter"
    assert stored.payload["reason"] == "409_without_ticket_id"
    # Finalized in place — no second create_ticket row spawned alongside it.
    assert (
        db_session.query(IngestionTask)
        .filter_by(conversation_id="thread1", task_type="create_ticket")
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_create_ticket_unit_not_found_increments_serial_correction_counter(db_session):
    task = _enqueue_create_ticket_task(db_session)

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=cs.TicketOutcome(kind="unit_not_found")),
    ):
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="gmail",
            mailbox="support@acme.com",
            conversation_id="thread1",
            payload={**_TICKET_ARGS, "unit_serial": "BADSN"},
        )

    # handle_create_ticket_task commits on its own session; drop this session's
    # identity-map copies so assertions read committed state.
    db_session.expire_all()

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.serial_correction_attempt_count == 1
    assert conversation.ticket_id is None
    assert len(_queued_replies(db_session)) == 1
    # Definitive for this serial: a corrected one arrives as a new turn and a new task.
    assert db_session.get(IngestionTask, task.id).status == "done"


@pytest.mark.asyncio
async def test_create_ticket_store_not_found_dead_letters_without_customer_message(db_session):
    task = _enqueue_create_ticket_task(db_session)

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=cs.TicketOutcome(kind="store_not_found")),
    ):
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="gmail",
            mailbox="support@acme.com",
            conversation_id="thread1",
            payload=_TICKET_ARGS,
        )

    # handle_create_ticket_task commits on its own session; drop this session's
    # identity-map copies so assertions read committed state.
    db_session.expire_all()

    assert _queued_replies(db_session) == []  # not customer-fixable — never surfaced as a re-ask
    stored = db_session.get(IngestionTask, task.id)
    assert stored.status == "dead_letter"
    assert stored.payload["reason"] == "STORE_NOT_FOUND"
    assert (
        db_session.query(IngestionTask)
        .filter_by(conversation_id="thread1", task_type="create_ticket")
        .count()
        == 1
    )


@pytest.mark.asyncio
async def test_create_ticket_partial_failure_rolls_back_ticket_id(db_session):
    """A committed ticket_id with no queued reply would be unrecoverable: the retry hits
    the ticket_id guard, no-ops, and the customer is never told. So the branch commits
    once, and a failure part-way through must leave nothing behind."""
    task = _enqueue_create_ticket_task(db_session)
    outcome = cs.TicketOutcome(kind="created", ticket_id="tk-1", ticket_number="FS-100")

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=outcome),
    ), patch(
        "app.services.conversation_service.enqueue_backfill",
        side_effect=RuntimeError("db blew up"),
    ):
        with pytest.raises(RuntimeError, match="db blew up"):
            await cs.handle_create_ticket_task(
                task_id=task.id,
                adapter="gmail",
                mailbox="support@acme.com",
                conversation_id="thread1",
                payload=_TICKET_ARGS,
            )

    db_session.expire_all()
    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.ticket_id is None
    assert _queued_replies(db_session) == []
    # Still retryable — and the retry can genuinely redo the whole branch.
    assert db_session.get(IngestionTask, task.id).status == "open"


@pytest.mark.asyncio
async def test_create_ticket_api_error_raises_so_the_worker_can_retry(db_session):
    """Transient failures must stay retryable rather than dead-lettering immediately."""
    task = _enqueue_create_ticket_task(db_session)

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=cs.TicketOutcome(kind="error", error_detail="boom")),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await cs.handle_create_ticket_task(
                task_id=task.id,
                adapter="gmail",
                mailbox="support@acme.com",
                conversation_id="thread1",
                payload=_TICKET_ARGS,
            )

    # Left as the worker found it — record_failure decides open vs dead_letter.
    assert db_session.get(IngestionTask, task.id).status == "open"


@pytest.mark.asyncio
async def test_create_ticket_task_is_a_noop_if_ticket_id_already_set(db_session):
    _seed_conversation(db_session, ticket_id="already-set")
    task = _enqueue_create_ticket_task(db_session)

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket", new=AsyncMock()
    ) as mock_api:
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="gmail",
            mailbox="support@acme.com",
            conversation_id="thread1",
            payload=_TICKET_ARGS,
        )

    # handle_create_ticket_task commits on its own session; drop this session's
    # identity-map copies so assertions read committed state.
    db_session.expire_all()

    assert mock_api.await_count == 0
    assert _queued_replies(db_session) == []
    assert db_session.get(IngestionTask, task.id).status == "done"


@pytest.mark.asyncio
async def test_round_cap_boundary_withholds_gathering_tools(db_session):
    _seed_conversation(db_session, question_round_count=5)

    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent("reply", reply_text="holding message"),
    ):
        await cs.handle_message_batch("thread1", [_message()])

    assert _fake_decision_agent.last_allow_gathering_tools is False


@pytest.mark.asyncio
async def test_escalation_sends_holding_message_and_dead_letters_synthesized_task(db_session):
    _seed_conversation(db_session, question_round_count=5)

    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent(None),  # model returns no tool call at all
    ):
        await cs.handle_message_batch("thread1", [_message()])

    assert len(_queued_replies(db_session)) == 1
    dead_letter = (
        db_session.query(IngestionTask)
        .filter_by(conversation_id="thread1", task_type="create_ticket")
        .one()
    )
    assert dead_letter.status == "dead_letter"


@pytest.mark.asyncio
async def test_non_compliant_tool_call_despite_cap_is_rejected_and_forces_escalation(db_session):
    """Defense in depth: allow_gathering_tools=False should already prevent this at the
    SDK level, but if the model somehow still returns ask_question/create_ticket, the
    call must not be trusted."""
    _seed_conversation(db_session, question_round_count=5)

    with patch(
        "app.services.decision_agent.DecisionAgent.run",
        new=_fake_decision_agent(
            "ask_question", ask_question_text="one more question", ask_question_reason="baseline"
        ),
    ):
        await cs.handle_message_batch("thread1", [_message()])

    conversation = db_session.query(Conversation).filter_by(conversation_id="thread1").one()
    assert conversation.question_round_count == 5  # not incremented — call was rejected
    dead_letter = (
        db_session.query(IngestionTask)
        .filter_by(conversation_id="thread1", task_type="create_ticket")
        .one()
    )
    assert dead_letter.status == "dead_letter"
    (dispatched_text,) = _queued_replies(db_session)
    assert dispatched_text != "one more question"


@pytest.mark.asyncio
async def test_post_ticket_message_is_a_deliberate_noop(db_session):
    _seed_conversation(db_session, ticket_id="already-set")

    with patch("app.services.decision_agent.DecisionAgent.run", new=AsyncMock()) as mock_agent:
        await cs.handle_message_batch("thread1", [_message()])

    assert mock_agent.await_count == 0
    assert _queued_replies(db_session) == []


# ---------------------------------------------------------------------------
# Receiving Mailbox address
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ticket_is_created_for_the_conversations_mailbox(db_session):
    """The receiving address is the Conversation's `mailbox` column."""
    conversation = Conversation(
        adapter="imap",
        mailbox="help@shop.com",
        conversation_id="thread1",
    )
    db_session.add(conversation)
    db_session.commit()
    task = TaskRepository(db_session).enqueue(
        task_type="create_ticket",
        mailbox_key=MailboxKey("imap", "help@shop.com"),
        conversation_id="thread1",
        payload=_TICKET_ARGS,
    )
    outcome = cs.TicketOutcome(kind="created", ticket_id="tk-1", ticket_number="FS-100")

    with patch(
        "app.services.ticket_client.TicketClient.create_ticket",
        new=AsyncMock(return_value=outcome),
    ) as mock_api:
        await cs.handle_create_ticket_task(
            task_id=task.id,
            adapter="imap",
            mailbox="help@shop.com",
            conversation_id="thread1",
            payload=_TICKET_ARGS,
        )

    assert mock_api.await_args.kwargs["receiving_inbox_address"] == "help@shop.com"
    db_session.expire_all()
    assert db_session.query(Conversation).count() == 1  # found by adapter + mailbox


def test_receiving_inbox_address_applies_the_test_override(monkeypatch):
    monkeypatch.setattr(
        cs.settings, "SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_FROM", "support@inbound-mailtrap.io"
    )
    monkeypatch.setattr(cs.settings, "SUPPORT_TEST_RECEIVING_INBOX_OVERRIDE_TO", "store@acme.com")
    conversation = Conversation(adapter="mailtrap", mailbox="support@inbound-mailtrap.io")

    assert cs._receiving_inbox_address(conversation) == "store@acme.com"
