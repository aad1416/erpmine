"""Seam 1 for the Gmail API adapter in push mode: the Pub/Sub webhook served by
`router()` and its token check, the backup poll that covers a dropped notification, and
watch renewal, with one Mailbox's failure never stopping the others."""

from __future__ import annotations

import asyncio
import base64
import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from app.support.adapter.gmail import webhook as webhook_module
from app.support.adapter.gmail.models import GmailWatch
from app.support.adapter.gmail.settings import gmail_settings
from tests.support.adapter.imap.harness import RecordingSink, eventually
from .conftest import add_mailbox
from .test_adapter import MAILBOX, OTHER_MAILBOX, more_reads

WEBHOOK_PATH = "/support/webhooks/gmail"


def _notification(email_address: str) -> dict:
    data = json.dumps({"emailAddress": email_address, "historyId": "999"}).encode()
    return {"message": {"data": base64.b64encode(data).decode(), "messageId": "1"}}


async def _post(adapter, body: dict, headers: dict | None = None) -> httpx.Response:
    app = FastAPI()
    app.include_router(adapter.router())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(WEBHOOK_PATH, json=body, headers=headers or {})


async def _started(running, *accounts):
    """Starts the adapter and waits for each Mailbox's first read (on start)."""
    sink = RecordingSink()
    adapter = await running(sink)
    for account in accounts:
        await eventually(lambda: account.history_reads >= 1)
    return adapter, sink


@pytest.mark.asyncio
async def test_a_push_notification_reads_the_notified_mailbox_only(
    push_mode, db_session, running
):
    notified = add_mailbox(db_session, push_mode, MAILBOX)
    other = add_mailbox(db_session, push_mode, OTHER_MAILBOX)
    adapter, sink = await _started(running, notified, other)
    notified.receive("msg-1")
    other.receive("msg-2")

    response = await _post(adapter, _notification("Support@Acme-Store.com"))

    assert response.status_code == 204
    await eventually(lambda: sink.delivered_ids() == ["msg-1"])
    assert other.history_reads == 1


@pytest.mark.asyncio
async def test_a_push_for_a_mailbox_not_served_here_reads_nothing(
    push_mode, db_session, running, caplog
):
    account = add_mailbox(db_session, push_mode, MAILBOX)
    adapter, _ = await _started(running, account)

    with caplog.at_level(logging.WARNING):
        response = await _post(adapter, _notification("someone@else.com"))

    assert response.status_code == 204
    assert "Gmail push for a Mailbox not served here: someone@else.com" in caplog.text
    assert account.history_reads == 1


@pytest.mark.asyncio
async def test_with_an_audience_set_the_webhook_needs_a_valid_google_token(
    push_mode, db_session, running, monkeypatch
):
    monkeypatch.setattr(gmail_settings, "PUBSUB_AUDIENCE", "https://support.example.com/push")
    verified = []

    def verify_oauth2_token(token, request, audience):
        verified.append((token, audience))
        if token != "good-token":
            raise ValueError("Token signature is invalid")
        return {"email": "pubsub@example.iam.gserviceaccount.com"}

    monkeypatch.setattr(webhook_module.id_token, "verify_oauth2_token", verify_oauth2_token)
    account = add_mailbox(db_session, push_mode, MAILBOX)
    adapter, sink = await _started(running, account)
    account.receive("msg-1")

    missing = await _post(adapter, _notification(MAILBOX))
    invalid = await _post(
        adapter, _notification(MAILBOX), headers={"Authorization": "Bearer bad-token"}
    )
    assert (missing.status_code, invalid.status_code) == (401, 401)
    await asyncio.sleep(0.05)  # time for a read the rejected pushes might have woken
    assert account.history_reads == 1

    valid = await _post(
        adapter, _notification(MAILBOX), headers={"Authorization": "Bearer good-token"}
    )

    assert valid.status_code == 204
    await eventually(lambda: sink.delivered_ids() == ["msg-1"])
    assert verified == [
        ("bad-token", "https://support.example.com/push"),
        ("good-token", "https://support.example.com/push"),
    ]


@pytest.mark.asyncio
async def test_without_an_audience_the_webhook_accepts_an_unauthenticated_push(
    push_mode, db_session, running, monkeypatch
):
    def verify_oauth2_token(*args, **kwargs):
        raise AssertionError("no token check without an audience")

    monkeypatch.setattr(webhook_module.id_token, "verify_oauth2_token", verify_oauth2_token)
    account = add_mailbox(db_session, push_mode, MAILBOX)
    adapter, sink = await _started(running, account)
    account.receive("msg-1")

    response = await _post(adapter, _notification(MAILBOX))

    assert response.status_code == 204
    await eventually(lambda: sink.delivered_ids() == ["msg-1"])


@pytest.mark.asyncio
async def test_the_backup_poll_picks_up_a_message_whose_push_was_dropped(
    push_mode, db_session, running, monkeypatch
):
    monkeypatch.setattr(gmail_settings, "BACKUP_POLL_INTERVAL_SECONDS", 0.05)
    # Push mode ignores the poll-mode interval.
    monkeypatch.setattr(gmail_settings, "POLL_INTERVAL_SECONDS", 3600)
    account = add_mailbox(db_session, push_mode, MAILBOX)
    _, sink = await _started(running, account)

    account.receive("msg-1")  # no notification arrives

    await eventually(lambda: sink.delivered_ids() == ["msg-1"])


@pytest.mark.asyncio
async def test_watches_are_renewed_on_start_and_stored_per_mailbox(
    push_mode, db_session, running
):
    first = add_mailbox(db_session, push_mode, MAILBOX)
    second = add_mailbox(db_session, push_mode, OTHER_MAILBOX)

    await _started(running, first, second)

    assert first.watches == second.watches == ["projects/p/topics/gmail"]
    db_session.expire_all()
    watches = {
        (watch.adapter, watch.mailbox, watch.history_id)
        for watch in db_session.query(GmailWatch).all()
    }
    assert watches == {("gmail", MAILBOX, "100"), ("gmail", OTHER_MAILBOX, "100")}


@pytest.mark.asyncio
async def test_a_watch_is_renewed_again_only_after_its_interval(
    push_mode, db_session, running, monkeypatch
):
    monkeypatch.setattr(gmail_settings, "BACKUP_POLL_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(gmail_settings, "WATCH_RENEWAL_INTERVAL_SECONDS", 0.5)
    account = add_mailbox(db_session, push_mode, MAILBOX)
    await _started(running, account)

    await more_reads(account)  # a few hundredths of a second
    assert account.watches == ["projects/p/topics/gmail"]

    await eventually(lambda: len(account.watches) == 2)


@pytest.mark.asyncio
async def test_a_failing_watch_renewal_does_not_stop_its_reads_or_other_mailboxes(
    push_mode, db_session, running, monkeypatch, caplog
):
    monkeypatch.setattr(gmail_settings, "BACKUP_POLL_INTERVAL_SECONDS", 0.01)
    failing = add_mailbox(db_session, push_mode, MAILBOX)
    failing.watch_error = RuntimeError("Pub/Sub topic permission denied")
    working = add_mailbox(db_session, push_mode, OTHER_MAILBOX)
    failing.receive("msg-1")
    working.receive("msg-2")

    with caplog.at_level(logging.ERROR):
        _, sink = await _started(running, failing, working)
        await eventually(lambda: sorted(sink.delivered_ids()) == ["msg-1", "msg-2"])

    assert working.watches == ["projects/p/topics/gmail"]
    assert f"Gmail Mailbox {MAILBOX}: watch renewal failed" in caplog.text
    # Retried on its next read, and renewed once it works.
    failing.watch_error = None
    await eventually(lambda: failing.watches == ["projects/p/topics/gmail"])


@pytest.mark.asyncio
async def test_poll_mode_registers_no_watch(gmail, db_session, running, monkeypatch):
    monkeypatch.setattr(gmail_settings, "PUBSUB_TOPIC", "projects/p/topics/gmail")
    account = add_mailbox(db_session, gmail, MAILBOX)

    await _started(running, account)
    await more_reads(account)

    assert account.watches == []
