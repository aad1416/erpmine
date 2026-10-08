"""Seam 1 for the Gmail API adapter, against a fake Gmail API: what reaches the sink,
the history cursor moving only with the outbox capture, crash recovery, and one Mailbox
failing without stopping the others."""

from __future__ import annotations

import logging

import pytest
from google.auth.exceptions import RefreshError

from app.support.adapter.gmail.settings import gmail_settings
from tests.support.adapter.imap.harness import RecordingSink, eventually
from .conftest import REFRESH_TOKEN, add_mailbox
from .fake_gmail import FakeGmailMailbox

MAILBOX = "support@acme-store.com"
OTHER_MAILBOX = "sales@acme-store.com"


async def more_reads(mailbox: FakeGmailMailbox, count=3):
    """Waits until `mailbox` has been read `count` more times, so the read that was
    running when this was called has finished."""
    target = mailbox.history_reads + count
    await eventually(lambda: mailbox.history_reads >= target)


@pytest.mark.asyncio
async def test_a_new_message_reaches_the_sink_normalized_under_its_mailbox(
    gmail, db_session, running
):
    account = add_mailbox(db_session, gmail, "Support@Acme-Store.com")
    account.receive("msg-1", thread_id="thread-1")
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["msg-1"])

    [message] = sink.delivered
    assert (message.adapter, message.mailbox) == ("gmail", MAILBOX)
    assert message.conversation_id == "thread-1"
    assert (message.sender_address, message.sender_name) == ("jane@example.com", "Jane Doe")
    assert message.subject == "Compressor noise"
    assert message.body_text == "The unit is making noise."
    # The Mailbox's own refresh token, with the app's OAuth client.
    assert (
        account.credentials.client_id,
        account.credentials.client_secret,
        account.credentials.refresh_token,
    ) == ("client-id", "client-secret", REFRESH_TOKEN)


@pytest.mark.asyncio
async def test_a_mailbox_without_a_cursor_starts_from_now(gmail, db_session, running):
    account = add_mailbox(db_session, gmail, MAILBOX, history_id=None)
    account.receive("before-start")
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: account.history_reads >= 1)
    account.receive("after-start")

    await eventually(lambda: sink.delivered_ids() == ["after-start"])


@pytest.mark.asyncio
async def test_our_own_sent_mail_is_skipped(gmail, db_session, running):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("our-reply", labels=("SENT",))
    account.receive("customer", labels=("INBOX",))
    sink = RecordingSink()

    await running(sink)

    await eventually(lambda: sink.delivered_ids() == ["customer"])
    await more_reads(account)
    assert sink.delivered_ids() == ["customer"]


@pytest.mark.asyncio
async def test_a_delivered_message_is_not_sunk_again_after_a_restart(gmail, db_session, running):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("msg-1")
    first_sink = RecordingSink()
    first = await running(first_sink)
    await eventually(lambda: first_sink.delivered_ids() == ["msg-1"])
    await first.stop()

    second_sink = RecordingSink()
    await running(second_sink)
    account.receive("msg-2")

    await eventually(lambda: second_sink.delivered_ids() == ["msg-2"])
    await more_reads(account)
    assert second_sink.delivered_ids() == ["msg-2"]
    assert account.fetches == ["msg-1", "msg-2"]


@pytest.mark.asyncio
async def test_an_undelivered_message_is_sunk_on_start_without_reading_it_again(
    gmail, db_session, running, monkeypatch
):
    """The first adapter captures the message but its sink never takes it (a crash
    between capture and handover). The cursor moved with the capture, so the next
    adapter doesn't fetch it from Gmail again: it re-sinks it from the outbox on start."""
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("msg-1")
    failing_sink = RecordingSink(fail_times=10**6)
    first = await running(failing_sink)
    await eventually(lambda: len(failing_sink.attempts) >= 1)
    await first.stop()
    assert failing_sink.delivered == []

    monkeypatch.setattr(gmail_settings, "POLL_INTERVAL_SECONDS", 3600)  # only start() delivers
    sink = RecordingSink()
    await running(sink)

    assert sink.delivered_ids() == ["msg-1"]
    assert account.fetches == ["msg-1"]


@pytest.mark.asyncio
async def test_a_failing_sink_is_retried_on_the_next_read(gmail, db_session, running):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("msg-1")
    sink = RecordingSink(fail_times=1)

    await running(sink)

    await eventually(lambda: sink.delivered_ids() == ["msg-1"])
    await more_reads(account)
    assert sink.delivered_ids() == ["msg-1"]
    assert account.fetches == ["msg-1"]


@pytest.mark.asyncio
async def test_a_message_that_fails_to_fetch_is_read_again_as_the_cursor_did_not_move(
    gmail, db_session, running
):
    account = add_mailbox(db_session, gmail, MAILBOX)
    account.receive("msg-1")
    account.receive("msg-2")
    account.fetch_errors["msg-2"] = 2
    sink = RecordingSink()

    await running(sink)

    await eventually(lambda: sink.delivered_ids() == ["msg-1", "msg-2"])
    assert account.fetches.count("msg-1") == 1


@pytest.mark.asyncio
async def test_an_expired_cursor_resyncs_from_now(gmail, db_session, running, caplog):
    account = add_mailbox(db_session, gmail, MAILBOX, history_id="5")
    account.oldest_history_id = 50
    account.receive("in-the-gap")
    sink = RecordingSink()

    with caplog.at_level(logging.WARNING):
        await running(sink)
        await eventually(lambda: account.history_reads >= 1)
        account.receive("after-resync")
        await eventually(lambda: sink.delivered_ids() == ["after-resync"])

    assert f"Gmail Mailbox {MAILBOX}: historyId 5 expired" in caplog.text


@pytest.mark.asyncio
async def test_a_revoked_mailbox_stops_while_the_others_keep_running(
    gmail, db_session, running, caplog
):
    revoked = add_mailbox(db_session, gmail, MAILBOX)
    revoked.fail = RefreshError("invalid_grant: Token has been expired or revoked.")
    working = add_mailbox(db_session, gmail, OTHER_MAILBOX)
    working.receive("msg-1")
    sink = RecordingSink()

    with caplog.at_level(logging.ERROR):
        await running(sink)
        await eventually(lambda: sink.delivered_ids() == ["msg-1"])
        working.receive("msg-2")
        await eventually(lambda: sink.delivered_ids() == ["msg-1", "msg-2"])

    [error] = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert error.getMessage().startswith(f"Gmail Mailbox {MAILBOX}: refresh token refused")


@pytest.mark.asyncio
async def test_a_mailbox_whose_reads_fail_does_not_stop_the_others(gmail, db_session, running):
    broken = add_mailbox(db_session, gmail, MAILBOX)
    broken.fail = RuntimeError("Gmail API unavailable")
    working = add_mailbox(db_session, gmail, OTHER_MAILBOX)
    working.receive("msg-1")
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["msg-1"])

    broken.fail = None
    broken.receive("msg-2")
    await eventually(lambda: sink.delivered_ids() == ["msg-1", "msg-2"])


@pytest.mark.asyncio
async def test_a_mailbox_without_a_refresh_token_is_not_served(
    gmail, db_session, running, caplog
):
    add_mailbox(db_session, gmail, MAILBOX, refresh_token=None)

    with caplog.at_level(logging.ERROR):
        adapter = await running(RecordingSink())

    assert f"Gmail Mailbox {MAILBOX} has no refresh token" in caplog.text
    with pytest.raises(LookupError):
        await adapter.send_message(MAILBOX, "thread-1", "Hi", idempotency_key="task-1")


@pytest.mark.asyncio
async def test_no_mailbox_is_served_without_the_apps_oauth_client(
    gmail, db_session, running, caplog, monkeypatch
):
    monkeypatch.setattr(gmail_settings, "CLIENT_SECRET", None)
    account = add_mailbox(db_session, gmail, MAILBOX)

    with caplog.at_level(logging.ERROR):
        await running(RecordingSink())

    assert "SUPPORT_GMAIL_CLIENT_ID and SUPPORT_GMAIL_CLIENT_SECRET" in caplog.text
    assert account.credentials is None
