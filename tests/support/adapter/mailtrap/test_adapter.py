"""Seam 1 for the Mailtrap adapter: driven only through `start(sink)`, `stop()` and
`send_message(...)`, with a fake sink and a fake Mailtrap API (`fake_mailtrap.py`).
Built with `MailtrapAdapter.load`, as the Mailbox Registry builds it."""

from __future__ import annotations

import asyncio

import pytest
from cryptography.fernet import Fernet

from app.config.setting import settings
from app.support.adapter.mailtrap import adapter as mailtrap_adapter_module
from app.support.adapter.mailtrap.adapter import MailtrapAdapter
from app.support.adapter.mailtrap.models import MailtrapMailbox
from app.support.adapter.mailtrap.settings import mailtrap_settings
from tests.support.adapter.mailtrap.fake_mailtrap import FakeMailtrap

FIRST_MAILBOX = "first@inbound-mailtrap.io"
SECOND_MAILBOX = "second@inbound-mailtrap.io"
CURSOR = "2024-01-01T00:00:00+00:00"


@pytest.fixture()
def mailtrap_api(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(mailtrap_settings, "POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(mailtrap_settings, "DETECTION_MODE", "poll")
    api = FakeMailtrap()
    monkeypatch.setattr(mailtrap_adapter_module, "MailtrapClient", api.client)
    return api


class RecordingSink:
    """Records every message it is given; `fail_times` makes the first calls raise."""

    def __init__(self, fail_times: int = 0) -> None:
        self.attempts: list = []
        self.delivered: list = []
        self._fail_times = fail_times

    async def __call__(self, message) -> None:
        self.attempts.append(message)
        if len(self.attempts) <= self._fail_times:
            raise RuntimeError("sink unavailable")
        self.delivered.append(message)

    def delivered_ids(self) -> list[str]:
        return [message.external_message_id for message in self.delivered]


def _add_mailbox(db_session, mailbox, inbox_id, api_token="token", cursor=CURSOR):
    db_session.add(
        MailtrapMailbox(mailbox=mailbox, inbox_id=inbox_id, api_token=api_token, cursor=cursor)
    )
    db_session.commit()


async def _eventually(predicate, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


async def _more_polls(inbox, count=3):
    """Waits until `inbox` has been polled `count` more times."""
    target = inbox.list_calls + count
    await _eventually(lambda: inbox.list_calls >= target)


@pytest.fixture()
async def running(db_session):
    """Starts adapters loaded from the test DB and stops them all on teardown."""
    started: list[MailtrapAdapter] = []

    async def start(sink) -> MailtrapAdapter:
        adapter = MailtrapAdapter.load(db_session)
        await adapter.start(sink)
        started.append(adapter)
        return adapter

    yield start
    for adapter in started:
        await adapter.stop()


@pytest.mark.asyncio
async def test_a_new_message_reaches_the_sink_normalized(mailtrap_api, db_session, running):
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("m1", "2024-01-02T00:00:00+00:00", thread_id="thread-1")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")
    sink = RecordingSink()

    await running(sink)
    await _eventually(lambda: len(sink.delivered) == 1)

    message = sink.delivered[0]
    assert (message.adapter, message.mailbox) == ("mailtrap", FIRST_MAILBOX)
    assert message.conversation_id == "thread-1"
    assert message.external_message_id == "m1"
    assert message.sender_address == "customer@example.com"
    assert message.body_text == "body m1"


@pytest.mark.asyncio
async def test_a_first_start_skips_the_backlog_and_delivers_only_new_mail(
    mailtrap_api, db_session, running
):
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("old", "2024-01-02T00:00:00+00:00")
    _add_mailbox(db_session, FIRST_MAILBOX, "816", cursor=None)
    sink = RecordingSink()

    await running(sink)
    await _more_polls(inbox)
    inbox.receive("new", "2024-01-03T00:00:00+00:00")
    await _eventually(lambda: len(sink.delivered) == 1)
    await _more_polls(inbox)

    assert sink.delivered_ids() == ["new"]


@pytest.mark.asyncio
async def test_messages_across_pages_are_delivered_oldest_first(
    mailtrap_api, db_session, running
):
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("before-cursor", "2023-12-31T00:00:00+00:00")
    for day in range(2, 7):
        inbox.receive(f"m{day}", f"2024-01-0{day}T00:00:00+00:00")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")
    sink = RecordingSink()

    await running(sink)
    await _eventually(lambda: len(sink.delivered) == 5)

    assert sink.delivered_ids() == ["m2", "m3", "m4", "m5", "m6"]


@pytest.mark.asyncio
async def test_a_message_is_redelivered_until_the_sink_returns_and_never_after(
    mailtrap_api, db_session, running
):
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("m1", "2024-01-02T00:00:00+00:00")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")
    failing_sink = RecordingSink(fail_times=1)

    adapter = await running(failing_sink)
    await _eventually(lambda: len(failing_sink.delivered) == 1)
    await _more_polls(inbox)
    await adapter.stop()

    assert [message.external_message_id for message in failing_sink.attempts] == ["m1", "m1"]

    # A restart reads the cursor back from the table: m1 is not handed over again.
    restarted_sink = RecordingSink()
    await running(restarted_sink)
    await _more_polls(inbox)
    inbox.receive("m2", "2024-01-03T00:00:00+00:00")
    await _eventually(lambda: len(restarted_sink.delivered) == 1)

    assert restarted_sink.delivered_ids() == ["m2"]


@pytest.mark.asyncio
async def test_messages_received_at_the_same_instant_are_not_lost_when_the_sink_fails(
    mailtrap_api, db_session, running
):
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("m1", "2024-01-02T00:00:00+00:00")
    inbox.receive("m2", "2024-01-02T00:00:00+00:00")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")
    sink = RecordingSink()
    original_call = sink.__class__.__call__
    failed = []

    async def fail_once_on_m2(message):
        if message.external_message_id == "m2" and not failed:
            failed.append(message)
            raise RuntimeError("sink unavailable")
        await original_call(sink, message)

    await running(fail_once_on_m2)
    await _eventually(lambda: "m2" in sink.delivered_ids())

    assert set(sink.delivered_ids()) == {"m1", "m2"}


@pytest.mark.asyncio
async def test_one_instance_serves_both_inboxes(mailtrap_api, db_session, running):
    first_inbox = mailtrap_api.add_inbox("816", "token-1")
    second_inbox = mailtrap_api.add_inbox("2551", "token-2")
    first_inbox.receive("first-m1", "2024-01-02T00:00:00+00:00")
    second_inbox.receive("second-m1", "2024-01-02T00:00:00+00:00")
    _add_mailbox(db_session, FIRST_MAILBOX, "816", api_token="token-1")
    _add_mailbox(db_session, SECOND_MAILBOX, "2551", api_token="token-2")
    sink = RecordingSink()

    await running(sink)
    await _eventually(lambda: len(sink.delivered) == 2)

    assert {(message.mailbox, message.external_message_id) for message in sink.delivered} == {
        (FIRST_MAILBOX, "first-m1"),
        (SECOND_MAILBOX, "second-m1"),
    }


@pytest.mark.asyncio
async def test_one_inbox_failing_does_not_stop_the_other(mailtrap_api, db_session, running):
    rejected_inbox = mailtrap_api.add_inbox("816", "rotated-token")
    healthy_inbox = mailtrap_api.add_inbox("2551", "token-2")
    rejected_inbox.receive("first-m1", "2024-01-02T00:00:00+00:00")
    _add_mailbox(db_session, FIRST_MAILBOX, "816", api_token="stale-token")
    _add_mailbox(db_session, SECOND_MAILBOX, "2551", api_token="token-2")
    # A row the seeder hasn't filled in yet is skipped, not fatal.
    db_session.add(MailtrapMailbox(mailbox="unseeded@inbound-mailtrap.io", cursor=CURSOR))
    db_session.commit()
    sink = RecordingSink()

    await running(sink)
    await _more_polls(rejected_inbox)  # still retried after failing
    healthy_inbox.receive("second-m1", "2024-01-02T00:00:00+00:00")
    await _eventually(lambda: len(sink.delivered) == 1)
    healthy_inbox.receive("second-m2", "2024-01-03T00:00:00+00:00")
    await _eventually(lambda: len(sink.delivered) == 2)

    assert sink.delivered_ids() == ["second-m1", "second-m2"]


@pytest.mark.asyncio
async def test_a_reply_goes_out_from_the_right_inbox_to_the_last_inbound_message(
    mailtrap_api, db_session, running
):
    first_inbox = mailtrap_api.add_inbox("816", "token-1")
    second_inbox = mailtrap_api.add_inbox("2551", "token-2")
    first_inbox.receive("first-m1", "2024-01-05T00:00:00+00:00", thread_id="t1")
    second_inbox.receive("older", "2024-01-02T00:00:00+00:00", thread_id="t1")
    second_inbox.receive("newer", "2024-01-03T00:00:00+00:00", thread_id="t1")
    second_inbox.receive("other-thread", "2024-01-04T00:00:00+00:00", thread_id="t2")
    _add_mailbox(db_session, FIRST_MAILBOX, "816", api_token="token-1")
    _add_mailbox(db_session, SECOND_MAILBOX, "2551", api_token="token-2")
    sink = RecordingSink()
    adapter = await running(sink)
    await _eventually(lambda: len(sink.delivered) == 4)

    await adapter.send_message(SECOND_MAILBOX, "t1", "On its way", idempotency_key="task-1")

    assert second_inbox.replies == [("newer", "On its way")]
    assert first_inbox.replies == []


@pytest.mark.asyncio
async def test_a_repeated_idempotency_key_sends_once(mailtrap_api, db_session, running):
    inbox = mailtrap_api.add_inbox("816", "token")
    inbox.receive("m1", "2024-01-02T00:00:00+00:00", thread_id="t1")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")
    sink = RecordingSink()
    adapter = await running(sink)
    await _eventually(lambda: len(sink.delivered) == 1)

    await adapter.send_message(FIRST_MAILBOX, "t1", "Hello", idempotency_key="task-1")
    await adapter.send_message(FIRST_MAILBOX, "t1", "Hello", idempotency_key="task-1")
    await adapter.send_message(FIRST_MAILBOX, "t1", "Hello again", idempotency_key="task-2")

    assert inbox.replies == [("m1", "Hello"), ("m1", "Hello again")]


@pytest.mark.asyncio
async def test_a_reply_without_an_inbound_message_or_mailbox_raises(
    mailtrap_api, db_session, running
):
    mailtrap_api.add_inbox("816", "token")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")
    adapter = await running(RecordingSink())

    with pytest.raises(ValueError, match="no inbound message"):
        await adapter.send_message(FIRST_MAILBOX, "no-such-thread", "Hi", idempotency_key="k1")
    with pytest.raises(LookupError):
        await adapter.send_message("unknown@x.com", "t1", "Hi", idempotency_key="k2")


@pytest.mark.asyncio
async def test_push_detection_mode_refuses_to_start(mailtrap_api, db_session, monkeypatch):
    monkeypatch.setattr(mailtrap_settings, "DETECTION_MODE", "push")
    mailtrap_api.add_inbox("816", "token")
    _add_mailbox(db_session, FIRST_MAILBOX, "816")

    with pytest.raises(RuntimeError, match="push is not implemented"):
        await MailtrapAdapter.load(db_session).start(RecordingSink())


@pytest.mark.asyncio
async def test_no_mailboxes_gives_an_idle_instance(mailtrap_api, db_session, running):
    adapter = await running(RecordingSink())

    assert adapter.router() is None
