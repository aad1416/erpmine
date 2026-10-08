"""Support monitoring API's read-only query layer: derived thread status/attention
flags, thread list filtering, and thread detail timeline merging + payload
normalization (see the plan this implements, okay-we-need-to-buzzing-journal.md)."""

from datetime import datetime, timedelta, UTC

import pytest
from fastapi import HTTPException

from app.config.setting import settings
from app.repositories.conversation_messages import ConversationMessageRepository
from app.repositories.conversations import ConversationRepository
from app.schemas.support_monitoring import ThreadStatus
from app.services import support_monitoring_service as svc
from app.support.adapter.mailbox_key import MailboxKey
from app.support.ingestion.models import TaskStatus, TaskType
from app.support.ingestion.task_repository import TaskRepository

MAILBOX = MailboxKey("gmail", "support@acme.com")


def _conversation(db_session, conversation_id="t1", mailbox_key=MAILBOX, **overrides):
    conversation = ConversationRepository(db_session).get_or_create(mailbox_key, conversation_id)
    for key, value in overrides.items():
        setattr(conversation, key, value)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


def _inbound(db_session, conversation, sender="cust@x.com", text="help", conv_id="t1", msg_id="m1"):
    from app.support.adapter.schemas import NormalizedMessage

    ConversationMessageRepository(db_session).add_inbound(
        conversation,
        [
            NormalizedMessage(
                adapter=conversation.adapter,
                mailbox=conversation.mailbox,
                conversation_id=conv_id,
                external_message_id=msg_id,
                sender_address=sender,
                received_at=datetime.now(UTC),
                body_text=text,
            )
        ],
    )


def _outbound(db_session, conversation, text="thanks"):
    ConversationMessageRepository(db_session).add_outbound(conversation, text)


# ---------------------------------------------------------------------------
# derive_status
# ---------------------------------------------------------------------------


def test_derive_status_ticketed_wins_over_everything_else(db_session):
    conversation = _conversation(db_session, ticket_id="TICKET-1")
    tasks = [
        TaskRepository(db_session).enqueue(
            task_type=TaskType.create_ticket.value,
            mailbox_key=MAILBOX,
            conversation_id="t1",
            payload={},
            status=TaskStatus.open.value,
        )
    ]
    status, needs_attention = svc.derive_status(conversation, tasks, None)
    assert status == ThreadStatus.ticketed
    assert needs_attention is False


def test_derive_status_escalated_by_round_cap(db_session):
    conversation = _conversation(
        db_session, question_round_count=settings.SUPPORT_QUESTION_ROUND_CAP, unit_serial=None
    )
    status, _ = svc.derive_status(conversation, [], None)
    assert status == ThreadStatus.escalated


def test_derive_status_not_escalated_if_capped_but_serial_known(db_session):
    """Cap exhaustion only means escalated when we still don't know the unit serial —
    matches conversation_service's own `capped` computation."""
    conversation = _conversation(
        db_session,
        question_round_count=settings.SUPPORT_QUESTION_ROUND_CAP,
        unit_serial="SN123",
    )
    status, _ = svc.derive_status(conversation, [], None)
    assert status != ThreadStatus.escalated


def test_derive_status_escalated_by_synthesized_dead_letter(db_session):
    conversation = _conversation(db_session)
    task = TaskRepository(db_session).synthesize_dead_letter(
        task_type=TaskType.create_ticket.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"reason": "escalation_cap_exhausted"},
    )
    status, needs_attention = svc.derive_status(conversation, [task], None)
    assert status == ThreadStatus.escalated
    assert needs_attention is True


def test_derive_status_in_progress_with_open_task(db_session):
    conversation = _conversation(db_session)
    task = TaskRepository(db_session).enqueue(
        task_type=TaskType.message.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={},
        status=TaskStatus.open.value,
    )
    status, _ = svc.derive_status(conversation, [task], None)
    assert status == ThreadStatus.in_progress


def test_derive_status_awaiting_customer_when_last_message_outbound(db_session):
    conversation = _conversation(db_session)
    status, _ = svc.derive_status(conversation, [], "outbound")
    assert status == ThreadStatus.awaiting_customer


def test_derive_status_new_with_no_messages_or_tasks(db_session):
    conversation = _conversation(db_session)
    status, needs_attention = svc.derive_status(conversation, [], None)
    assert status == ThreadStatus.new
    assert needs_attention is False


def test_derive_status_needs_attention_independent_of_status(db_session):
    """A ticketed thread whose confirmation send_message task dead-lettered is still
    'ticketed' (the ticket exists) but must surface as needing attention."""
    conversation = _conversation(db_session, ticket_id="TICKET-1")
    task = TaskRepository(db_session).enqueue(
        task_type=TaskType.send_message.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"text": "..."},
        status=TaskStatus.dead_letter.value,
    )
    status, needs_attention = svc.derive_status(conversation, [task], None)
    assert status == ThreadStatus.ticketed
    assert needs_attention is True


# ---------------------------------------------------------------------------
# resolve_store_mailboxes
# ---------------------------------------------------------------------------


class _FakeLyndomDB:
    def __init__(self, email):
        self._email = email

    def get_store_email(self, store_id):
        return self._email


def test_resolve_store_mailboxes_returns_every_mailbox_in_the_adapter_tables(db_session):
    """The per-store lookup is still commented out in the service, so every store
    resolves to every Mailbox in the Mailbox Adapters' tables — read from the tables, not
    the environment, and without decrypting a credential."""
    from app.support.adapter.gmail.models import GmailMailbox
    from app.support.adapter.imap.models import ImapMailbox
    from app.support.adapter.mailtrap.models import MailtrapMailbox

    db_session.add_all(
        [
            MailtrapMailbox(mailbox="support-tickets@inbound-mailtrap.io", inbox_id="816"),
            MailtrapMailbox(mailbox="second-inbox@inbound-mailtrap.io", inbox_id="2551"),
            ImapMailbox(mailbox="help@shop.com", store_id="store-a"),
            GmailMailbox(mailbox="support@acme.com"),
        ]
    )
    db_session.commit()

    mailboxes = svc.resolve_store_mailboxes(
        "store-1", _FakeLyndomDB("Support@Acme.com"), db_session
    )

    assert mailboxes == [
        MailboxKey("gmail", "support@acme.com"),
        MailboxKey("imap", "help@shop.com"),
        MailboxKey("mailtrap", "second-inbox@inbound-mailtrap.io"),
        MailboxKey("mailtrap", "support-tickets@inbound-mailtrap.io"),
    ]


def test_resolve_store_mailboxes_raises_503_when_no_mailbox_is_configured(db_session):
    with pytest.raises(HTTPException) as exc_info:
        svc.resolve_store_mailboxes("store-1", _FakeLyndomDB(None), db_session)
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# list_threads
# ---------------------------------------------------------------------------


def test_list_threads_is_scoped_to_the_given_mailboxes(db_session):
    conversation_a = _conversation(db_session, conversation_id="t1")
    _inbound(db_session, conversation_a, conv_id="t1")
    other = _conversation(
        db_session, conversation_id="t2", mailbox_key=MailboxKey("mailtrap", "dev@mailtrap.io")
    )
    _inbound(db_session, other, conv_id="t2")

    result = svc.list_threads(db_session, mailboxes=[MAILBOX])
    assert [item.conversation_id for item in result.items] == ["t1"]


def _three_mailboxes(db_session):
    """Same address on two adapters, and a second address on one of them."""
    for conversation_id, mailbox_key in (
        ("gmail-help", MailboxKey("gmail", "help@shop.com")),
        ("imap-help", MailboxKey("imap", "help@shop.com")),
        ("imap-sales", MailboxKey("imap", "sales@shop.com")),
    ):
        conversation = _conversation(
            db_session, conversation_id=conversation_id, mailbox_key=mailbox_key
        )
        _inbound(db_session, conversation, conv_id=conversation_id, msg_id=conversation_id)


def test_list_threads_filters_by_adapter(db_session):
    _three_mailboxes(db_session)

    result = svc.list_threads(db_session, adapter="imap")
    assert sorted(item.conversation_id for item in result.items) == ["imap-help", "imap-sales"]


def test_list_threads_filters_by_mailbox(db_session):
    _three_mailboxes(db_session)

    result = svc.list_threads(db_session, mailbox="Help@Shop.com")
    assert sorted(item.conversation_id for item in result.items) == ["gmail-help", "imap-help"]


def test_list_threads_filters_by_adapter_and_mailbox(db_session):
    _three_mailboxes(db_session)

    result = svc.list_threads(db_session, adapter="imap", mailbox="help@shop.com")
    assert [item.conversation_id for item in result.items] == ["imap-help"]


def test_thread_summary_shows_adapter_and_mailbox_separately(db_session):
    _three_mailboxes(db_session)

    result = svc.list_threads(db_session, adapter="imap", mailbox="sales@shop.com")
    (item,) = result.items
    assert (item.adapter, item.mailbox) == ("imap", "sales@shop.com")


def test_list_threads_filters_by_sender_email_substring(db_session):
    conversation = _conversation(db_session, conversation_id="t1")
    _inbound(db_session, conversation, sender="jane@customer.com", conv_id="t1")

    found = svc.list_threads(db_session, q="jane@")
    not_found = svc.list_threads(db_session, q="nomatch@")
    assert [item.conversation_id for item in found.items] == ["t1"]
    assert not_found.items == []


def test_list_threads_filters_by_status(db_session):
    ticketed = _conversation(db_session, conversation_id="t1", ticket_id="TICKET-1")
    _inbound(db_session, ticketed, conv_id="t1", msg_id="m1")
    in_progress = _conversation(db_session, conversation_id="t2")
    _inbound(db_session, in_progress, conv_id="t2", msg_id="m2")
    TaskRepository(db_session).enqueue(
        task_type=TaskType.message.value,
        mailbox_key=MAILBOX,
        conversation_id="t2",
        payload={},
        status=TaskStatus.open.value,
    )

    result = svc.list_threads(db_session, statuses=[ThreadStatus.ticketed])
    assert [item.conversation_id for item in result.items] == ["t1"]


def test_list_threads_filters_by_needs_attention(db_session):
    healthy = _conversation(db_session, conversation_id="t1")
    _inbound(db_session, healthy, conv_id="t1", msg_id="m1")
    attention = _conversation(db_session, conversation_id="t2")
    _inbound(db_session, attention, conv_id="t2", msg_id="m2")
    TaskRepository(db_session).enqueue(
        task_type=TaskType.send_message.value,
        mailbox_key=MAILBOX,
        conversation_id="t2",
        payload={"text": "x"},
        status=TaskStatus.dead_letter.value,
    )

    result = svc.list_threads(db_session, needs_attention=True)
    assert [item.conversation_id for item in result.items] == ["t2"]


def test_list_threads_pagination(db_session):
    for i in range(5):
        conversation = _conversation(db_session, conversation_id=f"t{i}")
        _inbound(db_session, conversation, conv_id=f"t{i}", msg_id=f"m{i}")

    page = svc.list_threads(db_session, limit=2, offset=0)
    assert page.total == 5
    assert len(page.items) == 2

    next_page = svc.list_threads(db_session, limit=2, offset=2)
    assert len(next_page.items) == 2
    assert {i.conversation_id for i in page.items}.isdisjoint(
        {i.conversation_id for i in next_page.items}
    )


# ---------------------------------------------------------------------------
# get_thread_detail
# ---------------------------------------------------------------------------


def test_get_thread_detail_returns_none_for_unknown_thread(db_session):
    assert svc.get_thread_detail(db_session, MailboxKey("gmail", "nope@x.com"), "missing") is None


def test_get_thread_detail_is_found_by_adapter_and_mailbox(db_session):
    _three_mailboxes(db_session)

    detail = svc.get_thread_detail(db_session, MailboxKey("imap", "help@shop.com"), "imap-help")
    assert (detail.adapter, detail.mailbox) == ("imap", "help@shop.com")
    other_adapter = MailboxKey("gmail", "help@shop.com")
    assert svc.get_thread_detail(db_session, other_adapter, "imap-help") is None


def test_get_thread_detail_merges_messages_and_tasks_in_time_order(db_session):
    conversation = _conversation(db_session, conversation_id="t1")
    now = datetime.now(UTC)

    _inbound(db_session, conversation, conv_id="t1", msg_id="m1")
    message = ConversationMessageRepository(db_session).get_all(conversation.id)[0]
    message.received_at = now
    db_session.commit()

    task = TaskRepository(db_session).enqueue(
        task_type=TaskType.send_message.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"text": "reply"},
        status=TaskStatus.done.value,
    )
    task.created_at = now + timedelta(seconds=5)
    db_session.commit()

    detail = svc.get_thread_detail(db_session, MAILBOX, "t1")
    assert [entry.kind for entry in detail.timeline] == ["message", "task"]


def test_get_thread_detail_normalizes_task_payloads_by_type(db_session):
    conversation = _conversation(db_session, conversation_id="t1")
    repo = TaskRepository(db_session)
    repo.enqueue(
        task_type=TaskType.message.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={
            "sender_address": "cust@x.com",
            "subject": "Broken unit",
            "body_text": "it broke",
        },
    )
    repo.enqueue(
        task_type=TaskType.create_ticket.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"unit_serial": "SN123", "title": "Broken unit"},
    )
    repo.enqueue(
        task_type=TaskType.send_message.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"text": "We're on it"},
    )

    detail = svc.get_thread_detail(db_session, MAILBOX, "t1")
    by_type = {entry.task_type: entry for entry in detail.timeline if entry.kind == "task"}

    assert by_type["message"].message_summary.subject == "Broken unit"
    assert by_type["create_ticket"].ticket_args.unit_serial == "SN123"
    assert by_type["send_message"].outbound_text == "We're on it"


def test_get_thread_detail_surfaces_last_error_and_dead_letter_reason(db_session):
    conversation = _conversation(db_session, conversation_id="t1")
    repo = TaskRepository(db_session)
    task = repo.enqueue(
        task_type=TaskType.create_ticket.value,
        mailbox_key=MAILBOX,
        conversation_id="t1",
        payload={"unit_serial": "SN123"},
    )
    repo.mark_dead_letter(task.id, payload_patch={"reason": "STORE_NOT_FOUND"})

    detail = svc.get_thread_detail(db_session, MAILBOX, "t1")
    entry = detail.timeline[0]
    assert entry.dead_letter_reason == "STORE_NOT_FOUND"
