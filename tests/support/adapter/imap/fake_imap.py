"""In-memory stand-in for an IMAP server, exposed through the slice of the IMAPClient
API that `ImapMailboxClient` uses. No real mail account needed. By default it is Gmail
(offers X-GM-EXT-1); built without that capability it is a standard server, which has no
Gmail IDs or labels and rejects fetching them.

The adapter calls it from worker threads while a test delivers mail from the event loop,
so every operation holds the server's lock. `FakeImapHosts` routes connections by host,
for several Mailboxes each on its own server."""

from __future__ import annotations

import imaplib
import socket
import threading
from dataclasses import dataclass, field
from datetime import date, datetime

from imapclient.exceptions import LoginError


@dataclass
class FakeStoredMessage:
    raw: bytes
    gm_msgid: int | None
    gm_thrid: int | None
    internal_date: datetime
    flags: set[bytes] = field(default_factory=set)
    labels: tuple[bytes, ...] = ()
    size: int | None = None  # RFC822.SIZE; len(raw) unless set


class FakeImapServer:
    def __init__(self, uidvalidity: int = 1, capabilities=(b"IMAP4REV1", b"X-GM-EXT-1")):
        self.uidvalidity = uidvalidity
        self.capabilities = set(capabilities)
        self.inbox: dict[int, FakeStoredMessage] = {}
        self.uidnext = 1
        self.logins: list[tuple[str, str]] = []
        self.connections = 0
        self.appended: list[tuple[str, bytes]] = []
        self.reject_login = False
        self.fetches: list[tuple[list[int], list[bytes]]] = []
        self.hang_on: str | None = None  # method name whose next `hangs` calls time out
        self.hangs = 0
        self.blocked_on: str | None = None  # method name whose calls wait for `unblock()`
        self._unblocked = threading.Event()
        self.selects = 0  # one per poll that reached INBOX
        self.lock = threading.RLock()
        self.connected_to: tuple | None = None  # (host, port, implicit TLS) of the last connect
        self.starttls = False

    def deliver(
        self,
        raw: bytes,
        gm_msgid: int | None,
        gm_thrid: int | None,
        internal_date: datetime,
        labels: tuple[bytes, ...] = (b"\\Inbox",),
        size: int | None = None,
    ) -> int:
        with self.lock:
            uid = self.uidnext
            self.uidnext += 1
            self.inbox[uid] = FakeStoredMessage(
                raw, gm_msgid, gm_thrid, internal_date, labels=labels, size=size
            )
            return uid

    def hang(self, method: str, times: int = 1) -> None:
        """The next `times` calls of `method` time out, as a hung step does."""
        self.hang_on, self.hangs = method, times

    def block(self, method: str) -> None:
        """Calls of `method` wait until `unblock()`: a server that stops answering."""
        self._unblocked.clear()
        self.blocked_on = method

    def unblock(self) -> None:
        self.blocked_on = None
        self._unblocked.set()

    def seen(self, uid: int) -> bool:
        with self.lock:
            return b"\\Seen" in self.inbox[uid].flags

    def body_fetches(self) -> list[int]:
        """UIDs whose body was fetched, in order."""
        with self.lock:
            return [uid for uids, items in self.fetches if b"BODY.PEEK[]" in items for uid in uids]

    def renumber(self, uidvalidity: int) -> None:
        """What a server does when UIDVALIDITY changes: every message gets a new UID."""
        with self.lock:
            self.uidvalidity = uidvalidity
            messages = [self.inbox[uid] for uid in sorted(self.inbox)]
            self.inbox = {uid: message for uid, message in enumerate(messages, start=1)}
            self.uidnext = len(messages) + 1

    def factory(self, host, port=None, ssl=True, timeout=None):
        with self.lock:
            self.connections += 1
            self.connected_to = (host, port, ssl)
            return FakeIMAPClient(self)


class FakeImapHosts:
    """An IMAP client factory that connects to the fake server registered for the host."""

    def __init__(self) -> None:
        self.servers: dict[str, FakeImapServer] = {}

    def add(self, host: str, server: FakeImapServer) -> FakeImapServer:
        self.servers[host] = server
        return server

    def factory(self, host, port=None, ssl=True, timeout=None):
        return self.servers[host].factory(host, port=port, ssl=ssl, timeout=timeout)


class FakeIMAPClient:
    def __init__(self, server: FakeImapServer):
        self._server = server
        self.normalise_times = True
        self._selected = False

    def _maybe_hang(self, method: str) -> None:
        if self._server.blocked_on == method:
            self._server._unblocked.wait()
        # IMAPClient's socket timeout turns a hung step into this exception.
        with self._server.lock:
            if self._server.hang_on == method and self._server.hangs > 0:
                self._server.hangs -= 1
                raise socket.timeout("timed out")

    def login(self, username, password):
        self._maybe_hang("login")
        self._server.logins.append((username, password))
        if self._server.reject_login:
            raise LoginError(b"[AUTHENTICATIONFAILED] Invalid credentials (Failure)")

    def starttls(self, ssl_context=None):
        self._server.starttls = True

    def noop(self):
        return (b"OK", [])

    def logout(self):
        pass

    def has_capability(self, capability):
        return capability.encode() in self._server.capabilities

    def select_folder(self, folder, readonly=False):
        assert folder == "INBOX"
        self._maybe_hang("select_folder")
        with self._server.lock:
            self._selected = True
            self._server.selects += 1
            return {b"UIDVALIDITY": self._server.uidvalidity, b"UIDNEXT": self._server.uidnext}

    def search(self, criteria="ALL"):
        assert self._selected
        self._maybe_hang("search")
        with self._server.lock:
            return self._search(criteria)

    def _search(self, criteria):
        uids = sorted(self._server.inbox)
        if criteria == ["ALL"]:
            return uids
        if criteria[0] == "SINCE":
            since: date = criteria[1]
            return [uid for uid in uids if self._server.inbox[uid].internal_date.date() >= since]
        assert criteria[0] == "UID"
        start = int(criteria[1].split(":")[0])
        matched = [uid for uid in uids if uid >= start]
        # RFC 3501: `n:*` always includes the highest UID, even when it's below n.
        if not matched and uids:
            matched = [uids[-1]]
        return matched

    def fetch(self, messages, data):
        assert self._selected
        self._maybe_hang("fetch")
        with self._server.lock:
            return self._fetch(messages, data)

    def _fetch(self, messages, data):
        self._server.fetches.append((list(messages), list(data)))
        if data == [b"RFC822.SIZE"]:
            return {
                uid: {b"RFC822.SIZE": self._server.inbox[uid].size or len(self._server.inbox[uid].raw)}
                for uid in messages
                if uid in self._server.inbox
            }
        assert b"BODY.PEEK[]" in data, "must never set \\Seen implicitly"
        if b"X-GM-EXT-1" not in self._server.capabilities and any(
            item.startswith(b"X-GM-") for item in data
        ):
            raise imaplib.IMAP4.error("FETCH command error: BAD [b'Invalid fetch attribute']")

        def items(stored: FakeStoredMessage) -> dict:
            available = {
                b"BODY.PEEK[]": (b"BODY[]", stored.raw),
                b"INTERNALDATE": (b"INTERNALDATE", stored.internal_date),
                b"X-GM-MSGID": (b"X-GM-MSGID", stored.gm_msgid),
                b"X-GM-THRID": (b"X-GM-THRID", stored.gm_thrid),
                b"X-GM-LABELS": (b"X-GM-LABELS", stored.labels),
            }
            return dict(available[item] for item in data)

        return {uid: items(self._server.inbox[uid]) for uid in messages if uid in self._server.inbox}

    def append(self, folder, msg, flags=(), msg_time=None):
        with self._server.lock:
            self._server.appended.append((folder, msg))

    def add_flags(self, messages, flags, silent=False):
        with self._server.lock:
            for uid in messages:
                self._server.inbox[uid].flags.update(flags)
