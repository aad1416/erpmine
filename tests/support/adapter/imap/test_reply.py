"""Seam 1 for IMAP replies over SMTP: threading headers, recipient, the right Mailbox,
threading after the outbox is purged, skipping our own sent mail, idempotent sends and
failures — against fake IMAP servers and a fake SMTP send."""

import asyncio
import logging
from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib
import pytest

from app.config.setting import settings
from app.support.adapter.imap.models import ImapOutboxMessage
from app.support.adapter.imap.smtp import reply_subject
from .fake_imap import FakeImapServer
from .harness import RecordingSink, eventually, more_polls
from .test_adapter import APP_PASSWORD, GMAIL_API_THREAD_ID, GM_THRID, MAILBOX, OTHER_MAILBOX

WHEN = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)


def _inbound(
    message_id,
    sender="Jane Doe <jane@example.com>",
    subject="Help",
    references=None,
    cc=None,
    body="My unit is broken.",
    to=MAILBOX,
):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    if cc:
        message["Cc"] = cc
    message["Subject"] = subject
    message["Message-ID"] = message_id
    if references:
        message["In-Reply-To"] = references[-1]
        message["References"] = " ".join(references)
    message.set_content(body)
    return message.as_bytes()


async def _start_with(imap, db_session, running, *raws, **mailbox_columns):
    """Starts the adapter on a Mailbox holding `raws` and waits until all are sunk."""
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7), **mailbox_columns)
    for index, raw in enumerate(raws, start=1):
        server.deliver(raw, index, GM_THRID, WHEN.replace(hour=9 + index))
    sink = RecordingSink()
    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == len(raws))
    return server, sink, adapter


@pytest.mark.asyncio
async def test_reply_threads_under_the_inbound_message(imap, db_session, running):
    raw = _inbound("<m2@example.com>", references=["<m0@example.com>", "<m1@example.com>"])
    _, _, adapter = await _start_with(imap, db_session, running, raw)

    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "We're on it.", idempotency_key="task-1")

    [mail] = imap.smtp.sent
    reply = mail.message
    assert reply["From"] == MAILBOX
    assert reply["Subject"] == "Re: Help"
    assert reply["In-Reply-To"] == "<m2@example.com>"
    assert reply["References"] == "<m0@example.com> <m1@example.com> <m2@example.com>"
    assert reply["Message-ID"].endswith("@acme-store.com>")
    assert reply.get_content().strip() == "We're on it."
    assert mail.sender == MAILBOX
    assert mail.options["hostname"] == "smtp.gmail.com"
    assert mail.options["port"] == 465
    assert mail.options["use_tls"] is True
    assert (mail.options["username"], mail.options["password"]) == (MAILBOX, APP_PASSWORD)


@pytest.mark.asyncio
async def test_reply_goes_only_to_the_last_inbound_sender(imap, db_session, running):
    _, _, adapter = await _start_with(
        imap,
        db_session,
        running,
        _inbound("<a@example.com>", cc="boss@example.com"),
        _inbound(
            "<b@example.com>",
            sender="Bob <bob@example.com>",
            subject="Re: Help",
            references=["<a@example.com>"],
            cc="jane@example.com, boss@example.com",
        ),
    )

    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Thanks.", idempotency_key="task-1")

    [mail] = imap.smtp.sent
    assert mail.recipients == ["bob@example.com"]
    assert mail.message["To"] == "bob@example.com"
    assert mail.message["Cc"] is None
    assert mail.message["In-Reply-To"] == "<b@example.com>"
    assert mail.message["References"] == "<a@example.com> <b@example.com>"
    assert mail.message["Subject"] == "Re: Help"


@pytest.mark.asyncio
async def test_reply_goes_out_from_the_mailbox_it_names(imap, db_session, running):
    """Two Mailboxes hold the same Gmail thread ID: the reply uses the named one's
    thread, address and app password."""
    first_server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    second_server = imap.add_mailbox(
        db_session,
        OTHER_MAILBOX,
        FakeImapServer(uidvalidity=7),
        imap_host="imap.other.test",
        app_password="other app password",
    )
    first_server.deliver(_inbound("<first@example.com>"), 1, GM_THRID, WHEN)
    second_server.deliver(
        _inbound("<second@example.com>", sender="bob@example.com", to=OTHER_MAILBOX),
        2,
        GM_THRID,
        WHEN,
    )
    sink = RecordingSink()
    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == 2)

    await adapter.send_message(
        OTHER_MAILBOX.upper(), GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1"
    )

    [mail] = imap.smtp.sent
    assert (mail.sender, mail.recipients) == (OTHER_MAILBOX, ["bob@example.com"])
    assert mail.message["In-Reply-To"] == "<second@example.com>"
    assert mail.options["password"] == "other app password"


@pytest.mark.parametrize(
    "subject, expected",
    [
        ("Help", "Re: Help"),
        ("Re: Help", "Re: Help"),
        ("RE: Help", "RE: Help"),
        ("re:Help", "re:Help"),
        ("Regarding my order", "Re: Regarding my order"),
        (None, "Re:"),
    ],
)
def test_reply_subject_adds_one_re_prefix(subject, expected):
    assert reply_subject(subject) == expected


@pytest.mark.asyncio
async def test_our_sent_reply_is_never_ingested(imap, db_session, running):
    server, sink, adapter = await _start_with(
        imap, db_session, running, _inbound("<m1@example.com>")
    )
    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")

    # The reply lands in INBOX (e.g. a provider that files sent mail there too).
    uid = server.deliver(imap.smtp.sent[0].message.as_bytes(), 2, GM_THRID, WHEN)
    await eventually(lambda: server.seen(uid))
    await more_polls(server)

    assert len(sink.attempts) == 1


@pytest.mark.asyncio
async def test_a_reply_smtp_accepted_before_a_timeout_is_still_known_as_ours(
    imap, db_session, running
):
    """The reply's Message-ID is recorded before sending, so a reply SMTP delivered
    while we never heard back is still skipped when it comes back in."""
    server, sink, adapter = await _start_with(
        imap, db_session, running, _inbound("<m1@example.com>")
    )
    delivered_anyway = []
    imap.smtp.on_send = delivered_anyway.append
    imap.smtp.fail_with = aiosmtplib.SMTPTimeoutError("timed out waiting for the reply")

    with pytest.raises(aiosmtplib.SMTPTimeoutError):
        await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")
    uid = server.deliver(delivered_anyway[0].as_bytes(), 2, GM_THRID, WHEN)
    await eventually(lambda: server.seen(uid))
    await more_polls(server)

    assert len(sink.attempts) == 1


@pytest.mark.asyncio
async def test_no_copy_is_saved_to_sent(imap, db_session, running):
    server, _, adapter = await _start_with(imap, db_session, running, _inbound("<m1@example.com>"))

    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")

    assert len(imap.smtp.sent) == 1
    assert server.appended == []


@pytest.mark.asyncio
async def test_reply_threads_after_the_outbox_row_is_purged(
    imap, db_session, running, monkeypatch
):
    monkeypatch.setattr(settings, "SUPPORT_RETENTION_DAYS", 0)
    server, _, adapter = await _start_with(imap, db_session, running, _inbound("<m1@example.com>"))
    # Past SUPPORT_RETENTION_DAYS the outbox row is gone; the threading table is not.
    await more_polls(server)
    db_session.expire_all()
    assert db_session.query(ImapOutboxMessage).count() == 0

    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Following up.", idempotency_key="task-1")

    [mail] = imap.smtp.sent
    assert mail.recipients == ["jane@example.com"]
    assert mail.message["In-Reply-To"] == "<m1@example.com>"


@pytest.mark.asyncio
async def test_a_repeated_idempotency_key_sends_once(imap, db_session, running):
    _, _, adapter = await _start_with(imap, db_session, running, _inbound("<m1@example.com>"))

    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hello", idempotency_key="task-1")
    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hello", idempotency_key="task-1")
    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hello again", idempotency_key="task-2")

    assert [mail.message.get_content().strip() for mail in imap.smtp.sent] == ["Hello", "Hello again"]


@pytest.mark.asyncio
async def test_a_failed_send_raises_and_its_retry_sends(imap, db_session, running):
    _, _, adapter = await _start_with(imap, db_session, running, _inbound("<m1@example.com>"))
    imap.smtp.fail_with = aiosmtplib.SMTPResponseException(535, "auth failed")

    with pytest.raises(aiosmtplib.SMTPResponseException):
        await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")
    assert imap.smtp.sent == []

    imap.smtp.fail_with = None
    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")
    assert len(imap.smtp.sent) == 1


@pytest.mark.asyncio
async def test_a_send_interrupted_mid_smtp_is_not_sent_again(
    imap, db_session, running, caplog
):
    """A crash (here, the worker cancelling the send) between SMTP and recording the
    result: the reply may have reached the customer, so a retry doesn't send it."""
    _, _, adapter = await _start_with(imap, db_session, running, _inbound("<m1@example.com>"))
    imap.smtp.fail_with = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")
    imap.smtp.fail_with = None
    with caplog.at_level(logging.WARNING):
        await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")

    assert imap.smtp.sent == []
    [warning] = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert "reply task-1" in warning.getMessage()
    assert "may or may not have reached the customer" in warning.getMessage()


@pytest.mark.asyncio
async def test_reply_to_an_unknown_conversation_or_mailbox_raises(imap, db_session, running):
    imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    adapter = await running(RecordingSink())

    with pytest.raises(LookupError):
        await adapter.send_message(MAILBOX, "deadbeef", "Hi", idempotency_key="task-1")
    with pytest.raises(LookupError):
        await adapter.send_message("unknown@acme-store.com", "deadbeef", "Hi", idempotency_key="task-2")
    assert imap.smtp.sent == []

    # The failed key was released: once the Conversation exists, its retry would send.
    with pytest.raises(LookupError):
        await adapter.send_message(MAILBOX, "deadbeef", "Hi", idempotency_key="task-1")


@pytest.mark.asyncio
async def test_starttls_mailbox_sends_with_starttls(imap, db_session, running):
    _, _, adapter = await _start_with(
        imap,
        db_session,
        running,
        _inbound("<m1@example.com>"),
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_tls_mode="starttls",
    )

    await adapter.send_message(MAILBOX, GMAIL_API_THREAD_ID, "Hi", idempotency_key="task-1")

    options = imap.smtp.sent[0].options
    assert (options["hostname"], options["port"]) == ("smtp.example.com", 587)
    assert (options["use_tls"], options["start_tls"]) == (False, True)
