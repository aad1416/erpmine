"""Seam 1 for Gmail API replies: from the right Mailbox, in the right thread, to the last
inbound sender, and once per idempotency key, including after an interrupted send."""

from __future__ import annotations

import logging

import pytest

from app.support.adapter.gmail.models import GmailSentReply
from app.support.adapter.gmail.settings import gmail_settings
from tests.support.adapter.imap.harness import RecordingSink, eventually
from .conftest import add_mailbox
from .test_adapter import MAILBOX, OTHER_MAILBOX, more_reads

REPLY_KEY_HEADER = "X-Support-Reply-Key"


@pytest.fixture()
def replying(gmail, running, monkeypatch):
    """Starts an adapter that reads once, on start, so replies are tested without reads
    in between."""
    monkeypatch.setattr(gmail_settings, "POLL_INTERVAL_SECONDS", 3600)

    async def start():
        return await running(RecordingSink())

    return start


@pytest.mark.asyncio
async def test_a_reply_goes_from_the_right_mailbox_in_the_thread_to_the_last_inbound_sender(
    gmail, db_session, replying
):
    account = add_mailbox(db_session, gmail, MAILBOX)
    other = add_mailbox(db_session, gmail, OTHER_MAILBOX)
    account.receive("m1", thread_id="thread-1", sender="Jane Doe <jane@example.com>")
    account.receive(
        "m2",
        thread_id="thread-1",
        sender="Bob <bob@example.com>",
        subject="Re: Compressor noise",
        rfc_message_id="<m2@example.com>",
        references="<m1@example.com>",
    )
    account.receive("m3", thread_id="thread-1", labels=("SENT",), sender=MAILBOX)
    account.receive("elsewhere", thread_id="thread-2", sender="carol@example.com")
    adapter = await replying()

    await adapter.send_message(
        "Support@Acme-Store.com", "thread-1", "We're on it.", idempotency_key="task-1"
    )

    [(reply, thread_id)] = account.sent
    assert thread_id == "thread-1"
    assert (reply["From"], reply["To"]) == (MAILBOX, "bob@example.com")
    assert reply["Subject"] == "Re: Compressor noise"
    assert reply["In-Reply-To"] == "<m2@example.com>"
    assert reply["References"] == "<m1@example.com> <m2@example.com>"
    assert reply[REPLY_KEY_HEADER] == "task-1"
    assert reply.get_content().strip() == "We're on it."
    assert other.sent == []


@pytest.mark.asyncio
async def test_a_first_reply_gets_a_re_subject(gmail, db_session, replying):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("m1", subject="Compressor noise")
    adapter = await replying()

    await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")

    [(reply, _)] = account.sent
    assert reply["Subject"] == "Re: Compressor noise"


@pytest.mark.asyncio
async def test_a_repeated_idempotency_key_sends_once(gmail, db_session, replying):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("m1")
    adapter = await replying()

    await adapter.send_message(MAILBOX, "thread-1", "Hello", idempotency_key="task-1")
    await adapter.send_message(MAILBOX, "thread-1", "Hello", idempotency_key="task-1")
    await adapter.send_message(MAILBOX, "thread-1", "Hello again", idempotency_key="task-2")

    assert [reply.get_content().strip() for reply in account.sent_in("thread-1")] == [
        "Hello",
        "Hello again",
    ]


@pytest.mark.asyncio
async def test_a_failed_send_raises_and_its_retry_sends_it(gmail, db_session, replying):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("m1")
    adapter = await replying()
    account.send_error = RuntimeError("Gmail API unavailable")

    with pytest.raises(RuntimeError):
        await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")
    assert account.sent == []

    account.send_error = None
    await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")

    assert len(account.sent_in("thread-1")) == 1


@pytest.mark.asyncio
async def test_a_send_that_reached_gmail_before_failing_is_not_sent_again(
    gmail, db_session, replying, caplog
):
    """The call raised (say, a timeout) after Gmail had sent the reply: the retry finds
    it in the thread by its idempotency key and marks it sent."""
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("m1")
    adapter = await replying()
    account.send_error = TimeoutError("read timed out")
    account.send_error_after_sending = True

    with pytest.raises(TimeoutError):
        await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")
    account.send_error = None

    with caplog.at_level(logging.INFO):
        await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")
        await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")

    assert len(account.sent_in("thread-1")) == 1
    assert "found in its thread; not sending it again" in caplog.text


@pytest.mark.asyncio
async def test_a_reply_left_sending_by_a_crash_is_sent_when_not_in_its_thread(
    gmail, db_session, replying, caplog
):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("m1")
    db_session.add(
        GmailSentReply(
            idempotency_key="task-1",
            mailbox=MAILBOX,
            conversation_id="thread-1",
            status="sending",
        )
    )
    db_session.commit()
    adapter = await replying()

    with caplog.at_level(logging.WARNING):
        await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")

    assert len(account.sent_in("thread-1")) == 1
    assert "reply task-1 was being sent when a previous attempt stopped" in caplog.text


@pytest.mark.asyncio
async def test_a_reply_to_a_mailbox_not_served_raises(gmail, db_session, replying):
    add_mailbox(db_session, gmail, MAILBOX)
    adapter = await replying()

    with pytest.raises(LookupError):
        await adapter.send_message("nobody@acme-store.com", "thread-1", "Hi", idempotency_key="t")


@pytest.mark.asyncio
async def test_our_sent_reply_is_not_read_back_in_as_a_customer_message(
    gmail, db_session, running
):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("m1")
    sink = RecordingSink()
    adapter = await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["m1"])

    await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")
    await more_reads(account)

    assert sink.delivered_ids() == ["m1"]
