"""Helpers for driving the IMAP adapter at Seam 1: a recording sink, waiting on the
adapter's background polls, and adding Mailbox Connection rows. The fixtures that use
them are in `conftest.py`."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.support.adapter.imap.models import ImapMailbox
from .fake_imap import FakeImapHosts, FakeImapServer
from .fake_smtp import FakeSmtp

GMAIL_IMAP_HOST = "imap.gmail.com"


class RecordingSink:
    """Records every message it is given; `fail_times` makes the first calls raise."""

    def __init__(self, fail_times: int = 0) -> None:
        self.attempts: list = []
        self.delivered: list = []
        self._fail_times = fail_times

    async def __call__(self, message) -> None:
        self.attempts.append(message)
        if len(self.attempts) <= self._fail_times:
            raise RuntimeError("sink unavailable")
        self.delivered.append(message)

    def delivered_ids(self) -> list[str]:
        return [message.external_message_id for message in self.delivered]


async def eventually(predicate, timeout=5.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


async def more_polls(server: FakeImapServer, count=3):
    """Waits until `server` has been polled `count` more times, so the poll that was
    running when this was called has finished."""
    target = server.selects + count
    await eventually(lambda: server.selects >= target)


@dataclass
class ImapWorld:
    """The fake Mail Providers the adapter under test connects to."""

    hosts: FakeImapHosts = field(default_factory=FakeImapHosts)
    smtp: FakeSmtp = field(default_factory=FakeSmtp)

    def add_mailbox(
        self,
        db_session,
        address: str,
        server: FakeImapServer,
        cursor: str | None = "7:0",
        app_password: str = "abcd efgh ijkl mnop",
        imap_host: str = GMAIL_IMAP_HOST,
        **columns,
    ) -> FakeImapServer:
        """Adds the Mailbox's row, reached at `imap_host` on `server`. Other columns
        default to Gmail's."""
        self.hosts.add(imap_host, server)
        db_session.add(
            ImapMailbox(
                mailbox=address,
                store_id=address,
                app_password=app_password,
                imap_host=imap_host,
                cursor=cursor,
                **columns,
            )
        )
        db_session.commit()
        return server
