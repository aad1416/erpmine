"""IMAP Mailboxes on Mail Providers without Gmail's extensions (Yahoo, Fastmail, iCloud,
self-hosted), at Seam 1: message IDs from the Message-ID header, Conversations linked by
In-Reply-To/References, and replies threaded over SMTP — against a fake standard IMAP
server (no X-GM-EXT-1) and a fake SMTP send. Gmail Mailboxes keep Gmail's IDs."""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest

from app.support.adapter.imap.normalize import new_conversation_id
from .fake_imap import FakeImapServer
from .harness import RecordingSink, eventually, more_polls
from .test_adapter import GMAIL_API_THREAD_ID, GM_THRID, MAILBOX

FASTMAIL = {
    "imap_host": "imap.fastmail.com",
    "imap_port": 143,
    "imap_tls_mode": "starttls",
    "smtp_host": "smtp.fastmail.com",
    "smtp_port": 587,
    "smtp_tls_mode": "starttls",
}
STANDARD_IMAP = (b"IMAP4REV1", b"UIDPLUS", b"IDLE")
# Recent, so a UIDVALIDITY rescan (last 3 days) finds it.
WHEN = datetime.now(UTC) - timedelta(hours=1)


def _email(
    message_id: str | None,
    subject="Help",
    in_reply_to: str | None = None,
    references: list[str] | None = None,
    sender="Jane Doe <jane@example.com>",
    body="My unit is broken.",
):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = MAILBOX
    message["Subject"] = subject
    message["Date"] = "Fri, 25 Sep 2026 09:00:00 +0000"
    if message_id is not None:
        message["Message-ID"] = message_id
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = " ".join(references)
    message.set_content(body)
    return message.as_bytes()


def _deliver(server, raw, minutes=0):
    return server.deliver(raw, None, None, WHEN + timedelta(minutes=minutes))


def _server(imap, db_session, uidvalidity=7):
    return imap.add_mailbox(
        db_session,
        MAILBOX,
        FakeImapServer(uidvalidity=uidvalidity, capabilities=STANDARD_IMAP),
        app_password="provider app password",
        **FASTMAIL,
    )


def _conversations(sink) -> dict[str, str]:
    return {message.external_message_id: message.conversation_id for message in sink.delivered}


@pytest.mark.asyncio
async def test_email_is_handed_over_and_our_reply_threads_under_it(imap, db_session, running):
    server = _server(imap, db_session)
    uid = _deliver(server, _email("<first@example.com>"))
    sink = RecordingSink()

    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)
    conversation_id = new_conversation_id("<first@example.com>")
    await adapter.send_message(MAILBOX, conversation_id, "We're on it.", idempotency_key="task-1")

    [message] = sink.delivered
    assert (message.adapter, message.mailbox) == ("imap", MAILBOX)
    assert message.external_message_id == "<first@example.com>"
    assert message.conversation_id == conversation_id
    assert server.seen(uid)
    # Host, port and TLS mode come from the Mailbox's row.
    assert server.connected_to == ("imap.fastmail.com", 143, False)
    assert server.starttls is True
    # Gmail's fetch items are never asked of a standard server (the fake rejects them).
    assert all(not item.startswith(b"X-GM-") for _, items in server.fetches for item in items)

    [mail] = imap.smtp.sent
    assert mail.recipients == ["jane@example.com"]
    assert mail.message["In-Reply-To"] == "<first@example.com>"
    assert mail.message["References"] == "<first@example.com>"
    assert mail.message["Subject"] == "Re: Help"
    options = mail.options
    assert (options["hostname"], options["port"]) == ("smtp.fastmail.com", 587)
    assert (options["use_tls"], options["start_tls"]) == (False, True)
    assert options["password"] == "provider app password"


@pytest.mark.asyncio
async def test_customer_reply_to_our_reply_joins_the_conversation(imap, db_session, running):
    server = _server(imap, db_session)
    _deliver(server, _email("<first@example.com>"))
    sink = RecordingSink()
    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)
    conversation_id = new_conversation_id("<first@example.com>")
    await adapter.send_message(MAILBOX, conversation_id, "Hi", idempotency_key="task-1")
    our_reply = imap.smtp.sent[0].message["Message-ID"]

    # Their client answers our reply: In-Reply-To names only our Message-ID.
    _deliver(
        server,
        _email(
            "<second@example.com>",
            subject="Re: Help",
            in_reply_to=our_reply,
            references=["<first@example.com>", our_reply],
        ),
        minutes=5,
    )
    await eventually(lambda: len(sink.delivered) == 2)

    assert _conversations(sink) == {
        "<first@example.com>": conversation_id,
        "<second@example.com>": conversation_id,
    }


@pytest.mark.asyncio
async def test_reply_found_through_older_references_joins_the_conversation(
    imap, db_session, running
):
    """In-Reply-To names mail we never saw (e.g. a CC'd colleague's message); an older
    References entry is ours."""
    server = _server(imap, db_session)
    _deliver(server, _email("<first@example.com>"))
    _deliver(
        server,
        _email(
            "<third@example.com>",
            in_reply_to="<unknown@elsewhere.com>",
            references=["<first@example.com>", "<unknown@elsewhere.com>"],
        ),
        minutes=5,
    )
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 2)

    conversation_id = new_conversation_id("<first@example.com>")
    assert _conversations(sink) == {
        "<first@example.com>": conversation_id,
        "<third@example.com>": conversation_id,
    }


@pytest.mark.asyncio
async def test_reply_with_only_in_reply_to_joins_the_conversation(imap, db_session, running):
    server = _server(imap, db_session)
    _deliver(server, _email("<first@example.com>"))
    _deliver(server, _email("<second@example.com>", in_reply_to="<first@example.com>"), minutes=5)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 2)

    assert set(_conversations(sink).values()) == {new_conversation_id("<first@example.com>")}


@pytest.mark.asyncio
async def test_same_subject_without_header_links_starts_a_new_conversation(
    imap, db_session, running
):
    server = _server(imap, db_session)
    _deliver(server, _email("<first@example.com>", subject="Order #1001"))
    _deliver(server, _email("<fresh@example.com>", subject="Order #1001"), minutes=5)
    _deliver(server, _email("<re@example.com>", subject="Re: Order #1001"), minutes=6)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 3)

    assert _conversations(sink) == {
        "<first@example.com>": new_conversation_id("<first@example.com>"),
        "<fresh@example.com>": new_conversation_id("<fresh@example.com>"),
        "<re@example.com>": new_conversation_id("<re@example.com>"),
    }


@pytest.mark.asyncio
async def test_reply_to_unknown_mail_starts_a_new_conversation(imap, db_session, running):
    server = _server(imap, db_session)
    _deliver(server, _email("<x@example.com>", in_reply_to="<never-seen@example.com>"))
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)

    assert _conversations(sink) == {"<x@example.com>": new_conversation_id("<x@example.com>")}


@pytest.mark.asyncio
async def test_message_without_message_id_is_handed_over_once(imap, db_session, running):
    server = _server(imap, db_session)
    _deliver(server, _email(None))
    sink = RecordingSink()

    # A normal poll, a restart, then a UIDVALIDITY change that rescans the last days:
    # the message is fetched again, and its hashed ID is the same.
    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)
    await adapter.stop()
    adapter = await running(sink)
    server.renumber(uidvalidity=8)
    await eventually(lambda: server.body_fetches().count(1) == 2)
    await more_polls(server)

    [message] = sink.delivered
    assert message.external_message_id.startswith("sha256:")
    assert message.conversation_id == new_conversation_id(message.external_message_id)

    # With no Message-ID to answer, the reply still reaches the customer, unthreaded.
    await adapter.send_message(MAILBOX, message.conversation_id, "Hi", idempotency_key="task-1")
    [mail] = imap.smtp.sent
    assert mail.recipients == ["jane@example.com"]
    assert mail.message["In-Reply-To"] is None


@pytest.mark.asyncio
async def test_different_messages_without_message_id_stay_apart(imap, db_session, running):
    server = _server(imap, db_session)
    _deliver(server, _email(None, subject="First"))
    _deliver(server, _email(None, subject="Second"), minutes=5)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 2)

    assert len(set(_conversations(sink).values())) == 2


@pytest.mark.asyncio
async def test_our_reply_and_mail_from_the_mailbox_are_skipped_without_labels(
    imap, db_session, running
):
    """No `\\Sent` or `\\Draft` labels here: our reply is known by its Message-ID, and
    anything else from the Mailbox's own address is skipped by From."""
    server = _server(imap, db_session)
    _deliver(server, _email("<first@example.com>"))
    sink = RecordingSink()
    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)
    await adapter.send_message(
        MAILBOX, new_conversation_id("<first@example.com>"), "Hi", idempotency_key="task-1"
    )

    reply_uid = _deliver(server, imap.smtp.sent[0].message.as_bytes(), minutes=1)
    draft_uid = _deliver(server, _email("<draft@acme-store.com>", sender=MAILBOX), minutes=2)
    await eventually(lambda: server.seen(reply_uid) and server.seen(draft_uid))
    await more_polls(server)

    assert sink.delivered_ids() == ["<first@example.com>"]


@pytest.mark.asyncio
async def test_gmail_mailbox_keeps_gmail_ids_even_with_header_links(imap, db_session, running):
    """On a server with X-GM-EXT-1, IDs are Gmail's, whatever the headers say."""
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7), **FASTMAIL)
    server.deliver(_email("<first@example.com>"), 1, GM_THRID, WHEN)
    server.deliver(_email("<other@example.com>", in_reply_to="<first@example.com>"), 2, 3, WHEN)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 2)

    assert _conversations(sink) == {"1": GMAIL_API_THREAD_ID, "2": "3"}
