"""Seam 1 for the IMAP adapter: cursor seeding, UID filtering, capture-then-mark-read,
crash recovery through its outbox, and one instance serving several Mailboxes. Driven
only through `start(sink)`, `stop()` and `send_message(...)`, against fake IMAP servers
and a fake SMTP send, with the adapter built by `ImapAdapter.load` as the Mailbox
Registry builds it."""

import logging
from datetime import UTC, datetime
from email.message import EmailMessage

import pytest

from app.support.adapter.imap.adapter import ImapAdapter
from app.support.adapter.imap.models import ImapMailbox, ImapOutboxMessage
from app.support.adapter.imap.normalize import normalize_imap_message
from app.support.adapter.mailbox_key import MailboxKey
from .fake_imap import FakeImapServer
from .harness import RecordingSink, eventually, more_polls

MAILBOX = "support@acme-store.com"
MAILBOX_KEY = MailboxKey("imap", MAILBOX)
OTHER_MAILBOX = "sales@acme-store.com"
APP_PASSWORD = "abcd efgh ijkl mnop"

# X-GM-MSGID / X-GM-THRID values and the Gmail API `id` / `threadId` for the same email.
GM_MSGID, GMAIL_API_ID = 1278455344230334865, "11bdfc5cae0c8191"
GM_THRID, GMAIL_API_THREAD_ID = 1266894439832287888, "1194e9c7de1efa90"


def _email(body="My unit is broken.", subject="Help", to=MAILBOX):
    message = EmailMessage()
    message["From"] = "Jane Doe <jane@example.com>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message.as_bytes()


def _deliver(server, msgid=GM_MSGID, thrid=GM_THRID, **kwargs):
    return server.deliver(_email(**kwargs), msgid, thrid, datetime(2026, 9, 25, 9, 0, tzinfo=UTC))


@pytest.mark.asyncio
async def test_a_new_message_reaches_the_sink_with_gmail_api_ids_and_is_marked_read(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    uid = _deliver(server)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)

    [message] = sink.delivered
    assert message.external_message_id == GMAIL_API_ID
    assert message.conversation_id == GMAIL_API_THREAD_ID
    assert message.mailbox_key == MAILBOX_KEY
    assert message.sender_address == "jane@example.com"
    assert server.seen(uid)
    assert uid in server.inbox  # stays in INBOX


@pytest.mark.asyncio
async def test_the_mailbox_is_stored_lower_cased_and_logs_in_with_its_app_password(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, "Support@Acme-Store.com", FakeImapServer(uidvalidity=7))
    _deliver(server)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)

    assert (sink.delivered[0].adapter, sink.delivered[0].mailbox) == ("imap", MAILBOX)
    assert server.logins == [(MAILBOX, APP_PASSWORD)]


@pytest.mark.asyncio
async def test_a_mailbox_row_defaults_to_gmail_servers(imap, db_session, running):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))

    await running(RecordingSink())
    await more_polls(server)

    assert server.connected_to == ("imap.gmail.com", 993, True)
    row = db_session.get(ImapMailbox, MAILBOX)
    assert (row.smtp_host, row.smtp_port, row.smtp_tls_mode) == ("smtp.gmail.com", 465, "ssl")


@pytest.mark.asyncio
async def test_a_first_start_skips_the_backlog_and_delivers_only_new_mail(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7), cursor=None)
    old_uids = [_deliver(server, msgid=1), _deliver(server, msgid=2)]
    sink = RecordingSink()

    await running(sink)
    await more_polls(server)
    new_uid = _deliver(server, msgid=3)
    await eventually(lambda: len(sink.delivered) == 1)
    await more_polls(server)

    assert sink.delivered_ids() == ["3"]
    assert not any(server.seen(uid) for uid in old_uids)
    assert server.seen(new_uid)


@pytest.mark.asyncio
async def test_a_first_start_on_an_empty_inbox_delivers_the_first_message(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7), cursor=None)
    sink = RecordingSink()

    await running(sink)
    await more_polls(server)
    _deliver(server, msgid=1)

    await eventually(lambda: sink.delivered_ids() == ["1"])


@pytest.mark.asyncio
async def test_no_new_mail_delivers_nothing(imap, db_session, running):
    """`UID 2:*` returns UID 1 when nothing is newer; it must be filtered out."""
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7), cursor="7:1")
    _deliver(server)
    sink = RecordingSink()

    await running(sink)
    await more_polls(server)

    assert sink.attempts == []


@pytest.mark.asyncio
async def test_one_connection_is_reused_across_polls(imap, db_session, running):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))

    await running(RecordingSink())
    await more_polls(server, count=5)

    assert server.connections == 1
    assert server.logins == [(MAILBOX, APP_PASSWORD)]


@pytest.mark.asyncio
async def test_a_message_is_redelivered_until_the_sink_returns_and_never_after(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    _deliver(server, msgid=1)
    failing_sink = RecordingSink(fail_times=1)

    adapter = await running(failing_sink)
    await eventually(lambda: len(failing_sink.delivered) == 1)
    await more_polls(server)
    await adapter.stop()

    assert [message.external_message_id for message in failing_sink.attempts] == ["1", "1"]

    # A restart reads the cursor and outbox back from the tables: nothing is handed
    # over again.
    restarted_sink = RecordingSink()
    await running(restarted_sink)
    await more_polls(server)
    _deliver(server, msgid=2)
    await eventually(lambda: len(restarted_sink.delivered) == 1)

    assert restarted_sink.delivered_ids() == ["2"]


def _outbox_row(mailbox_key, external_message_id, status):
    raw = _email(body=f"body {external_message_id}", to=mailbox_key.mailbox)
    message = normalize_imap_message(
        mailbox_key,
        raw,
        external_message_id=external_message_id,
        conversation_id="t1",
        received_at=datetime(2026, 9, 25, 9, 0, tzinfo=UTC),
    )
    return ImapOutboxMessage(
        mailbox=mailbox_key.mailbox,
        external_message_id=external_message_id,
        normalized_payload=message.model_dump(mode="json"),
        status=status,
    )


@pytest.mark.asyncio
async def test_start_re_sinks_undelivered_messages_before_polling(imap, db_session, running):
    """As a crash between capture and the sink leaves them: the cursor is already past
    these messages, so only the outbox still has them."""
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7), cursor="7:5")
    other_server = imap.add_mailbox(
        db_session, OTHER_MAILBOX, FakeImapServer(uidvalidity=7), imap_host="imap.other.test"
    )
    db_session.add_all(
        [
            _outbox_row(MAILBOX_KEY, "delivered-before-crash", "delivered"),
            _outbox_row(MAILBOX_KEY, "captured-1", "captured"),
            _outbox_row(MailboxKey("imap", OTHER_MAILBOX), "captured-2", "captured"),
        ]
    )
    db_session.commit()
    sink = RecordingSink()

    await running(sink)

    # Before start returned, so before any poll.
    assert sink.delivered_ids() == ["captured-1", "captured-2"]
    assert sink.delivered[0].body_text == "body captured-1"
    await more_polls(server)
    await more_polls(other_server)
    assert sink.delivered_ids() == ["captured-1", "captured-2"]


@pytest.mark.asyncio
async def test_an_undelivered_message_whose_sink_fails_at_start_is_retried_by_the_poll(
    imap, db_session, running
):
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    db_session.add(_outbox_row(MAILBOX_KEY, "captured-1", "captured"))
    db_session.commit()
    sink = RecordingSink(fail_times=1)

    await running(sink)
    await eventually(lambda: sink.delivered_ids() == ["captured-1"])
    await more_polls(server)

    assert sink.delivered_ids() == ["captured-1"]


@pytest.mark.asyncio
async def test_one_instance_serves_both_mailboxes(imap, db_session, running):
    first_server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    second_server = imap.add_mailbox(
        db_session, OTHER_MAILBOX, FakeImapServer(uidvalidity=9), imap_host="imap.other.test"
    )
    _deliver(first_server, msgid=1)
    _deliver(second_server, msgid=2, to=OTHER_MAILBOX)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 2)

    assert {(message.mailbox, message.external_message_id) for message in sink.delivered} == {
        (MAILBOX, "1"),
        (OTHER_MAILBOX, "2"),
    }


@pytest.mark.asyncio
async def test_a_rejected_password_stops_only_that_mailbox(imap, db_session, running, caplog):
    rejected_server = FakeImapServer(uidvalidity=7)
    rejected_server.reject_login = True
    imap.add_mailbox(db_session, MAILBOX, rejected_server)
    working_server = imap.add_mailbox(
        db_session, OTHER_MAILBOX, FakeImapServer(uidvalidity=9), imap_host="imap.other.test"
    )
    _deliver(rejected_server, msgid=1)
    _deliver(working_server, msgid=2, to=OTHER_MAILBOX)
    sink = RecordingSink()

    with caplog.at_level(logging.ERROR):
        await running(sink)
        await eventually(lambda: sink.delivered_ids() == ["2"])
        await more_polls(working_server)

    [error] = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert MAILBOX in error.getMessage()
    assert "login rejected" in error.getMessage()
    assert "Polling of this Mailbox is stopped" in error.getMessage()

    # The stopped Mailbox never retries its login, so Google doesn't lock it out.
    _deliver(working_server, msgid=3, to=OTHER_MAILBOX)
    await eventually(lambda: sink.delivered_ids() == ["2", "3"])
    assert len(rejected_server.logins) == 1


@pytest.mark.asyncio
async def test_a_new_app_password_and_a_restart_resume_a_rejected_mailbox(
    imap, db_session, running
):
    server = FakeImapServer(uidvalidity=7)
    server.reject_login = True
    imap.add_mailbox(db_session, MAILBOX, server)
    _deliver(server, msgid=1)
    adapter = await running(RecordingSink())
    await eventually(lambda: len(server.logins) == 1)
    await adapter.stop()

    server.reject_login = False
    row = db_session.get(ImapMailbox, MAILBOX)
    row.app_password = "new app password"
    db_session.commit()
    sink = RecordingSink()
    await running(sink)

    await eventually(lambda: sink.delivered_ids() == ["1"])
    assert server.logins[-1] == (MAILBOX, "new app password")


@pytest.mark.asyncio
async def test_a_hung_server_does_not_hold_up_another_mailbox(imap, db_session, running):
    hung_server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    working_server = imap.add_mailbox(
        db_session, OTHER_MAILBOX, FakeImapServer(uidvalidity=9), imap_host="imap.other.test"
    )
    hung_server.block("search")
    _deliver(hung_server, msgid=1)
    sink = RecordingSink()
    try:
        await running(sink)
        await eventually(lambda: hung_server.selects == 1)

        _deliver(working_server, msgid=2, to=OTHER_MAILBOX)
        await eventually(lambda: sink.delivered_ids() == ["2"])
    finally:
        hung_server.unblock()

    await eventually(lambda: sorted(sink.delivered_ids()) == ["1", "2"])


@pytest.mark.asyncio
async def test_a_mailbox_without_an_app_password_is_not_served(
    imap, db_session, running, caplog
):
    """As the migration leaves a row until the seeder fills in its app password."""
    db_session.add(ImapMailbox(mailbox="unseeded@acme-store.com", store_id="unseeded", cursor="7:0"))
    db_session.commit()
    server = imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))
    _deliver(server)
    sink = RecordingSink()

    adapter = await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)

    assert "IMAP Mailbox unseeded@acme-store.com has no app password" in caplog.text
    with pytest.raises(LookupError):
        await adapter.send_message("unseeded@acme-store.com", "t1", "Hi", idempotency_key="k1")


@pytest.mark.asyncio
async def test_no_mailboxes_gives_an_idle_instance(imap, db_session, running):
    adapter = await running(RecordingSink())

    assert isinstance(adapter, ImapAdapter)
    assert any(route.path == "/support/mailboxes/imap" for route in adapter.router().routes)
