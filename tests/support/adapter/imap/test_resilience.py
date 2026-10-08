"""The IMAP adapter keeps each Mailbox running through failures: a changed UIDVALIDITY,
a large backlog, a hung step, and oversized and failing messages — at Seam 1, against
fake IMAP servers. A rejected login and a hung server are in `test_adapter.py`, beside
the other multi-Mailbox tests. A Mailbox also configured for the Gmail API is refused by
the Mailbox Registry (`tests/support/test_support_system.py`)."""

import re
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest

from app.support.adapter.imap import adapter as imap_adapter
from app.support.adapter.imap.client import ImapMailboxClient, PasswordAuthenticator
from .fake_imap import FakeImapServer
from .harness import RecordingSink, eventually, more_polls
from .test_adapter import MAILBOX


def _email(body="My unit is broken.", subject="Help"):
    message = EmailMessage()
    message["From"] = "Jane Doe <jane@example.com>"
    message["To"] = MAILBOX
    message["Subject"] = subject
    message.set_content(body)
    return message.as_bytes()


def _deliver(server, n, days_ago=0, body="My unit is broken.", **kwargs):
    """Message `n` gets X-GM-MSGID and X-GM-THRID `n`, so its Gmail API id is hex(n)."""
    received = datetime.now(UTC) - timedelta(days=days_ago)
    return server.deliver(_email(body=body), n, n, received, **kwargs)


@pytest.mark.asyncio
async def test_uidvalidity_change_rescans_last_three_days_without_duplicates(
    imap, db_session, running, caplog
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    _deliver(server, 1, days_ago=5)
    _deliver(server, 2, days_ago=1)
    sink = RecordingSink()
    await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["1", "2"])
    await more_polls(server)

    # The server renumbers every message, and new mail arrives.
    with server.lock:
        server.renumber(uidvalidity=8)
        _deliver(server, 3)
        server.fetches.clear()
    await eventually(lambda: len(sink.delivered) == 3)
    await more_polls(server)

    # Only the last 3 days were re-read: message 1 (5 days old, now UID 1) was not, and
    # message 2 was not handed over again.
    assert set(server.body_fetches()) == {2, 3}
    assert "UIDVALIDITY changed 7 -> 8" in caplog.text
    assert sink.delivered_ids() == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_uidvalidity_change_with_no_recent_mail_restarts_at_current_position(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=8), cursor="7:5")
    _deliver(server, 1, days_ago=10)
    sink = RecordingSink()

    await running(sink)
    await more_polls(server)
    _deliver(server, 2)
    await eventually(lambda: len(sink.delivered) == 1)

    assert sink.delivered_ids() == ["2"]


@pytest.mark.asyncio
async def test_backlog_is_taken_200_per_poll_oldest_first(imap, db_session, running):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    for n in range(1, 251):
        _deliver(server, n)
    polls_at_handover = []

    async def sink(message):
        polls_at_handover.append((int(message.external_message_id, 16), server.selects))

    await running(sink)
    await eventually(lambda: len(polls_at_handover) == 250)

    assert [n for n, _ in polls_at_handover] == list(range(1, 251))
    first_poll = polls_at_handover[0][1]
    assert {poll for n, poll in polls_at_handover if n <= 200} == {first_poll}
    assert {poll for n, poll in polls_at_handover if n > 200} == {first_poll + 1}


@pytest.mark.asyncio
async def test_hung_step_times_out_and_next_poll_recovers(imap, db_session, running, caplog):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    uid = _deliver(server, 1)
    # More timeouts in a row than a failing message is allowed: a timeout is not the
    # message's fault, so no attempt is counted against it.
    server.hang("fetch", times=imap_adapter.MAX_ATTEMPTS + 1)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["1"])

    assert f"IMAP Mailbox {MAILBOX}: poll failed" in caplog.text
    assert "skipping it" not in caplog.text
    # Each timed-out connection was dropped and the next poll reconnected.
    assert server.connections == imap_adapter.MAX_ATTEMPTS + 2
    assert server.seen(uid)


def test_real_imap_connection_times_out_on_a_silent_server():
    """The timeout reaches IMAPClient's socket: a server that never answers raises."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    accepted = []
    threading.Thread(target=lambda: accepted.append(listener.accept()), daemon=True).start()
    client = ImapMailboxClient(
        host="127.0.0.1",
        port=listener.getsockname()[1],
        tls_mode="starttls",
        authenticator=PasswordAuthenticator("a", "b"),
        timeout=0.3,
    )

    started = time.monotonic()
    with pytest.raises(OSError):
        client.open_inbox()
    assert time.monotonic() - started < 5
    listener.close()


@pytest.mark.asyncio
async def test_oversized_and_repeatedly_failing_messages_are_skipped_and_later_mail_arrives(
    imap, db_session, running, monkeypatch, caplog
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    oversized = _deliver(server, 1, size=26 * 1024 * 1024)
    failing = _deliver(server, 2, body="poison")
    later = _deliver(server, 3)
    real_normalize = imap_adapter.normalize_imap_message

    def normalize(mailbox_key, raw, **kwargs):
        if b"poison" in raw:
            raise ValueError("unparseable")
        return real_normalize(mailbox_key, raw, **kwargs)

    monkeypatch.setattr(imap_adapter, "normalize_imap_message", normalize)
    sink = RecordingSink()

    # A restart after the first failure: the attempt count is kept with the cursor.
    adapter = await running(sink)
    await eventually(lambda: "attempt 1 of 3" in caplog.text)
    await adapter.stop()
    await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["3"])

    attempts_logged = re.findall(rf"UID {failing} failed \(attempt (\d) of 3\)", caplog.text)
    assert attempts_logged == ["1", "2"]
    assert f"UID {failing} failed 3 times, skipping it" in caplog.text
    assert f"skipping UID {oversized}, 27262976 bytes is over the 26214400 byte limit" in caplog.text
    # The oversized body is never downloaded.
    assert oversized not in server.body_fetches()
    assert not server.seen(oversized)
    assert not server.seen(failing)
    assert server.seen(later)

