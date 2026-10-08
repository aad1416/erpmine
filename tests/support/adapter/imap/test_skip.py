"""IMAP adapter at Seam 1: mail that is not from a customer (drafts, sent mail, mail
from the Mailbox itself, auto-replies, bounces) is marked read, never handed to the sink,
and doesn't hold the cursor back — against a fake IMAP server, one representative raw
email per rule."""

import logging
from datetime import UTC, datetime

import pytest

from .fake_imap import FakeImapServer
from .harness import RecordingSink, eventually, more_polls
from .test_adapter import MAILBOX

WHEN = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)

CUSTOMER = b"""\
From: Jane Doe <jane@example.com>
To: support@acme-store.com
Subject: Help
Message-ID: <customer-1@example.com>
Content-Type: text/plain; charset=utf-8

My unit is broken.
"""

SENT = b"""\
From: support@acme-store.com
To: Jane Doe <jane@example.com>
Subject: Re: Help
Message-ID: <sent-elsewhere@acme-store.com>
Content-Type: text/plain; charset=utf-8

We're on it.
"""

DRAFT = b"""\
From: support@acme-store.com
To: jane@example.com
Subject: Unfinished
Message-ID: <draft-1@acme-store.com>
Content-Type: text/plain; charset=utf-8

Half-written
"""

# From the Mailbox (different case) with no labels, as on a non-Gmail server.
FROM_MAILBOX = b"""\
From: Acme Support <SUPPORT@acme-store.com>
To: support@acme-store.com
Subject: Note to self
Message-ID: <self-1@acme-store.com>
Content-Type: text/plain; charset=utf-8

Reminder.
"""

AUTO_SUBMITTED = b"""\
From: Bob <bob@example.com>
To: support@acme-store.com
Subject: Out of office: Re: Your order
Auto-Submitted: auto-replied
Message-ID: <ooo-1@example.com>
Content-Type: text/plain; charset=utf-8

I'm away until Monday.
"""

X_AUTOREPLY = b"""\
From: Bob <bob@example.com>
To: support@acme-store.com
Subject: Auto: Re: Your order
X-Autoreply: yes
Message-ID: <ooo-2@example.com>
Content-Type: text/plain; charset=utf-8

I'm away until Monday.
"""


def _precedence(value: str) -> bytes:
    return f"""\
From: News <news@example.com>
To: support@acme-store.com
Subject: Weekly digest
Precedence: {value}
Message-ID: <prec-{value}@example.com>
Content-Type: text/plain; charset=utf-8

Digest.
""".encode()


EMPTY_RETURN_PATH = b"""\
Return-Path: <>
From: Mail Delivery System <delivery@mx.example.net>
To: support@acme-store.com
Subject: Undelivered Mail
Message-ID: <bounce-1@mx.example.net>
In-Reply-To: <reply-1@acme-store.com>
Content-Type: text/plain; charset=utf-8

Your message could not be delivered.
"""

MAILER_DAEMON = b"""\
From: Mail Delivery Subsystem <MAILER-DAEMON@googlemail.com>
To: support@acme-store.com
Subject: Delivery Status Notification (Failure)
Message-ID: <bounce-2@googlemail.com>
Content-Type: text/plain; charset=utf-8

Address not found.
"""

POSTMASTER = b"""\
From: postmaster@example.org
To: support@acme-store.com
Subject: Delivery failure
Message-ID: <bounce-3@example.org>
Content-Type: text/plain; charset=utf-8

Mailbox full.
"""

# A DSN from an ordinary-looking sender, recognisable only by its report structure.
DELIVERY_STATUS_REPORT = b"""\
From: Mail System <notices@mx.example.net>
To: support@acme-store.com
Subject: Returned mail
Message-ID: <bounce-4@mx.example.net>
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b1"

--b1
Content-Type: text/plain; charset=utf-8

Delivery to jane@example.com failed permanently.

--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; mx.example.net

Final-Recipient: rfc822; jane@example.com
Action: failed
Status: 5.1.1

--b1
Content-Type: text/rfc822-headers

From: support@acme-store.com
To: jane@example.com
Subject: Re: Help
Message-ID: <reply-2@acme-store.com>

--b1--
"""


def _server(imap, db_session):
    return imap.add_mailbox(db_session, MAILBOX, FakeImapServer(uidvalidity=7))


SKIPPED = [
    pytest.param(SENT, (b"\\Sent",), id="sent-label"),
    pytest.param(DRAFT, (b"\\Draft",), id="draft-label"),
    pytest.param(FROM_MAILBOX, (), id="from-mailbox-address"),
    pytest.param(AUTO_SUBMITTED, (b"\\Inbox",), id="auto-submitted"),
    pytest.param(X_AUTOREPLY, (b"\\Inbox",), id="x-autoreply"),
    pytest.param(_precedence("bulk"), (b"\\Inbox",), id="precedence-bulk"),
    pytest.param(_precedence("auto_reply"), (b"\\Inbox",), id="precedence-auto_reply"),
    pytest.param(_precedence("junk"), (b"\\Inbox",), id="precedence-junk"),
    pytest.param(EMPTY_RETURN_PATH, (b"\\Inbox",), id="bounce-empty-return-path"),
    pytest.param(MAILER_DAEMON, (b"\\Inbox",), id="bounce-mailer-daemon"),
    pytest.param(POSTMASTER, (b"\\Inbox",), id="bounce-postmaster"),
    pytest.param(DELIVERY_STATUS_REPORT, (b"\\Inbox",), id="bounce-delivery-status"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("raw, labels", SKIPPED)
async def test_non_customer_mail_is_skipped_marked_read_and_passed_by_the_cursor(
    imap, db_session, running, raw, labels
):
    server = _server(imap, db_session)
    skipped_uid = server.deliver(raw, 1, 1, WHEN, labels=labels)
    customer_uid = server.deliver(CUSTOMER, 2, 2, WHEN)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)
    await more_polls(server)

    assert sink.delivered_ids() == ["2"]
    assert server.seen(skipped_uid)
    assert server.seen(customer_uid)
    assert server.body_fetches() == [skipped_uid, customer_uid]  # never fetched again


@pytest.mark.asyncio
async def test_customer_email_without_markers_is_handed_over(imap, db_session, running):
    server = _server(imap, db_session)
    uid = server.deliver(CUSTOMER, 1, 1, WHEN)
    sink = RecordingSink()

    await running(sink)
    await eventually(lambda: len(sink.delivered) == 1)

    assert sink.delivered[0].sender_address == "jane@example.com"
    assert server.seen(uid)


@pytest.mark.asyncio
async def test_auto_submitted_no_is_customer_mail(imap, db_session, running):
    server = _server(imap, db_session)
    server.deliver(
        CUSTOMER.replace(b"Subject: Help\n", b"Subject: Help\nAuto-Submitted: no\n"), 1, 1, WHEN
    )
    sink = RecordingSink()

    await running(sink)

    await eventually(lambda: len(sink.delivered) == 1)


@pytest.mark.parametrize(
    "raw, original_message_id",
    [
        (DELIVERY_STATUS_REPORT, "<reply-2@acme-store.com>"),  # from the returned headers
        (EMPTY_RETURN_PATH, "<reply-1@acme-store.com>"),  # from In-Reply-To
        (MAILER_DAEMON, "(unknown Message-ID)"),
    ],
)
@pytest.mark.asyncio
async def test_bounce_is_logged_with_mailbox_and_original_message_id(
    imap, db_session, running, caplog, raw, original_message_id
):
    server = _server(imap, db_session)
    uid = server.deliver(raw, 1, 1, WHEN)
    sink = RecordingSink()

    with caplog.at_level(logging.WARNING, logger="app.support.adapter.imap.adapter"):
        await running(sink)
        await eventually(lambda: server.seen(uid))

    [record] = [record for record in caplog.records if "bounce" in record.getMessage()]
    assert record.levelno == logging.WARNING
    assert MAILBOX in record.getMessage()
    assert original_message_id in record.getMessage()
    assert sink.attempts == []


@pytest.mark.asyncio
async def test_skipped_mail_does_not_block_the_cursor_or_get_refetched(
    imap, db_session, running
):
    server = _server(imap, db_session)
    server.deliver(MAILER_DAEMON, 1, 1, WHEN)
    server.deliver(CUSTOMER, 2, 2, WHEN)
    server.deliver(AUTO_SUBMITTED, 3, 3, WHEN)
    sink = RecordingSink()

    adapter = await running(sink)
    await eventually(lambda: all(server.seen(uid) for uid in (1, 2, 3)))
    await adapter.stop()
    await running(sink)  # a restart reads the cursor back
    await more_polls(server)

    assert sink.delivered_ids() == ["2"]
    assert server.body_fetches() == [1, 2, 3]
