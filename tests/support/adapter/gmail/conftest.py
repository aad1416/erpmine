"""Fixtures for the Gmail adapter's Seam 1 tests: a fake Gmail API in place of the
network, and adapters loaded from the test DB as the Mailbox Registry loads them."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config.setting import settings
from app.support.adapter.gmail import adapter as gmail_adapter_module
from app.support.adapter.gmail.adapter import GmailAdapter
from app.support.adapter.gmail.models import GmailMailbox
from app.support.adapter.gmail.settings import gmail_settings
from .fake_gmail import FakeGmail

REFRESH_TOKEN = "gmail-refresh-token-under-test"


@pytest.fixture()
def gmail(db_session, monkeypatch) -> FakeGmail:
    """Poll mode, polling quickly, with the app's OAuth client configured."""
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    for name, value in {
        "CLIENT_ID": "client-id",
        "CLIENT_SECRET": "client-secret",
        "DETECTION_MODE": "poll",
        "POLL_INTERVAL_SECONDS": 0.01,
        "BACKUP_POLL_INTERVAL_SECONDS": 3600,
        "PUBSUB_TOPIC": None,
        "PUBSUB_AUDIENCE": None,
        "WATCH_RENEWAL_INTERVAL_SECONDS": 3600,
        "TIMEOUT_SECONDS": 5,
    }.items():
        monkeypatch.setattr(gmail_settings, name, value)
    world = FakeGmail()
    monkeypatch.setattr(gmail_adapter_module, "GmailClient", world.factory)
    return world


@pytest.fixture()
def push_mode(gmail, monkeypatch) -> FakeGmail:
    """Push mode with a topic, and a backup poll too slow to fire during a test."""
    monkeypatch.setattr(gmail_settings, "DETECTION_MODE", "push")
    monkeypatch.setattr(gmail_settings, "PUBSUB_TOPIC", "projects/p/topics/gmail")
    return gmail


def add_mailbox(
    db_session,
    world: FakeGmail,
    address: str,
    history_id: str | None = "100",
    refresh_token: str | None = REFRESH_TOKEN,
):
    """Adds the Mailbox's row and its fake Gmail account."""
    mailbox = world.add(address)
    db_session.add(GmailMailbox(mailbox=address, refresh_token=refresh_token, history_id=history_id))
    db_session.commit()
    return mailbox


@pytest.fixture()
async def running(db_session):
    """Starts an adapter loaded from the test DB, and stops every one on teardown."""
    started: list[GmailAdapter] = []

    async def start(sink) -> GmailAdapter:
        adapter = GmailAdapter.load(db_session)
        started.append(adapter)
        await adapter.start(sink)
        return adapter

    yield start
    for adapter in started:
        await adapter.stop()
