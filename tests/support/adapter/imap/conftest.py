"""Fixtures for the IMAP adapter's Seam 1 tests: fake IMAP servers and a fake SMTP send
in place of the network, and adapters loaded from the test DB as the Mailbox Registry
loads them."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config.setting import settings
from app.support.adapter.imap import adapter as imap_adapter_module
from app.support.adapter.imap.adapter import ImapAdapter
from app.support.adapter.imap.settings import imap_settings
from .harness import ImapWorld


@pytest.fixture()
def imap(db_session, monkeypatch) -> ImapWorld:
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(imap_settings, "POLL_INTERVAL_SECONDS", 0.01)
    world = ImapWorld()
    monkeypatch.setattr(imap_adapter_module, "IMAPClient", world.hosts.factory)
    monkeypatch.setattr(imap_adapter_module, "aiosmtplib_send", world.smtp.send)
    return world


@pytest.fixture()
async def running(db_session):
    """Starts an adapter loaded from the test DB, and stops every one on teardown."""
    started: list[ImapAdapter] = []

    async def start(sink) -> ImapAdapter:
        adapter = ImapAdapter.load(db_session)
        started.append(adapter)
        await adapter.start(sink)
        return adapter

    yield start
    for adapter in started:
        await adapter.stop()
