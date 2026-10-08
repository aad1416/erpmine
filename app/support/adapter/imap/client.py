"""Blocking IMAPClient wrapper for one Mailbox (ADR 0002).

One connection per Mailbox, reused across polls. The IMAP adapter holds one client per
Mailbox and uses it from that Mailbox's poll loop only. Every call here blocks, so the
adapter runs each one off the event loop.

Login goes through `ImapAuthenticator`; only the app-password implementation exists
today, so OAuth (XOAUTH2) can be added later as a second implementation. A rejected login
(e.g. the app password was revoked by a Google password change) is remembered on the
client: it never tries that login again, so a Mailbox with a bad password isn't retried
into a Google lockout. The next start builds a new client, which tries again.

Every IMAP step (connect, each command) is bounded by the socket timeout given to the
client. A step that hangs raises; the adapter drops the connection and the next poll
reconnects.
"""

from __future__ import annotations

import logging
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from imapclient import IMAPClient
from imapclient import SEEN
from imapclient.exceptions import LoginError

logger = logging.getLogger(__name__)

INBOX = "INBOX"
GMAIL_EXTENSION = "X-GM-EXT-1"

_FETCH_ITEMS = [b"BODY.PEEK[]", b"INTERNALDATE"]
_GMAIL_FETCH_ITEMS = [b"X-GM-MSGID", b"X-GM-THRID", b"X-GM-LABELS"]


class MailboxLoginRejected(Exception):
    """The server refused this Mailbox's credentials. Raised on the failed login and on
    every later use of the same client, which never tries to log in again."""


class ImapAuthenticator(Protocol):
    def authenticate(self, imap: IMAPClient) -> None: ...


@dataclass(frozen=True)
class PasswordAuthenticator:
    """App-password login (ADR 0002)."""

    username: str
    password: str

    def authenticate(self, imap: IMAPClient) -> None:
        imap.login(self.username, self.password)


@dataclass(frozen=True)
class FetchedMessage:
    uid: int
    raw: bytes
    internal_date: datetime
    # Gmail's IDs and labels (e.g. "\\Sent", "\\Draft"); None and empty on a server
    # without X-GM-EXT-1.
    gm_msgid: int | None = None
    gm_thrid: int | None = None
    labels: frozenset[str] = frozenset()


def _labels(value) -> frozenset[str]:
    return frozenset(
        label.decode("utf-8", errors="replace") if isinstance(label, bytes) else str(label)
        for label in value or ()
    )


class InboxSession:
    """INBOX, selected read-write on a live connection, from `ImapMailboxClient.open_inbox`.
    Valid until the client's connection is dropped."""

    def __init__(self, imap: IMAPClient, select_info: dict) -> None:
        self._imap = imap
        self.gmail_extensions: bool = imap.has_capability(GMAIL_EXTENSION)
        self.uidvalidity: int = int(select_info[b"UIDVALIDITY"])
        uidnext = select_info.get(b"UIDNEXT")
        self.uidnext: int = int(uidnext) if uidnext is not None else self._uidnext_from_search()

    def _uidnext_from_search(self) -> int:
        uids = self._imap.search(["ALL"])
        return max(uids) + 1 if uids else 1

    def uids_after(self, last_uid: int, limit: int) -> list[int]:
        """The oldest `limit` UIDs above `last_uid`, ascending. `UID n:*` always matches
        the newest message even when its UID is below n, hence the explicit filter."""
        uids = sorted(uid for uid in self._imap.search(["UID", f"{last_uid + 1}:*"]) if uid > last_uid)
        return uids[:limit]

    def first_uid_since(self, day: date) -> int | None:
        """The lowest UID whose INTERNALDATE is on or after `day`, or None."""
        uids = self._imap.search(["SINCE", day])
        return min(uids) if uids else None

    def sizes(self, uids: list[int]) -> dict[int, int]:
        """RFC822.SIZE in bytes per UID; a UID expunged meanwhile is missing."""
        if not uids:
            return {}
        response = self._imap.fetch(uids, [b"RFC822.SIZE"])
        return {uid: int(data[b"RFC822.SIZE"]) for uid, data in response.items()}

    def fetch(self, uid: int) -> FetchedMessage | None:
        """One message, read without setting \\Seen. None if it was expunged meanwhile.
        Gmail's IDs and labels are fetched only when the server offers X-GM-EXT-1; on
        Gmail, a message missing its IDs raises."""
        items = _FETCH_ITEMS + (_GMAIL_FETCH_ITEMS if self.gmail_extensions else [])
        data = self._imap.fetch([uid], items).get(uid)
        if data is None:
            return None
        gmail = self.gmail_extensions
        return FetchedMessage(
            uid=uid,
            raw=data[b"BODY[]"],
            internal_date=data[b"INTERNALDATE"],
            gm_msgid=int(data[b"X-GM-MSGID"]) if gmail else None,
            gm_thrid=int(data[b"X-GM-THRID"]) if gmail else None,
            labels=_labels(data.get(b"X-GM-LABELS")) if gmail else frozenset(),
        )

    def mark_read(self, uid: int) -> None:
        self._imap.add_flags([uid], [SEEN], silent=True)


class ImapMailboxClient:
    def __init__(
        self,
        host: str,
        port: int,
        tls_mode: str,
        authenticator: ImapAuthenticator,
        timeout: float,
        imap_factory: Callable[..., IMAPClient] = IMAPClient,
    ) -> None:
        self._host = host
        self._port = port
        self._tls_mode = tls_mode
        self._authenticator = authenticator
        self._timeout = timeout
        self._imap_factory = imap_factory
        self._imap: IMAPClient | None = None
        self.login_rejected: str | None = None  # the server's refusal, once login fails

    def _connect(self) -> IMAPClient:
        implicit_tls = self._tls_mode == "ssl"
        imap = self._imap_factory(
            self._host, port=self._port, ssl=implicit_tls, timeout=self._timeout
        )
        if not implicit_tls:
            imap.starttls(ssl.create_default_context())
        # Timezone-aware INTERNALDATE instead of naive local time.
        imap.normalise_times = False
        try:
            self._authenticator.authenticate(imap)
        except LoginError as error:
            self.login_rejected = str(error) or type(error).__name__
            try:
                imap.logout()
            except Exception:
                pass
            raise MailboxLoginRejected(self.login_rejected) from error
        return imap

    def _live_connection(self) -> IMAPClient:
        if self._imap is not None:
            try:
                self._imap.noop()
                return self._imap
            except Exception:
                logger.info("IMAP connection to %s went stale, reconnecting", self._host)
                self.drop_connection()
        self._imap = self._connect()
        return self._imap

    def open_inbox(self) -> InboxSession:
        """INBOX selected read-write, on the live connection or a new one. Any error
        drops the connection so the next call starts clean."""
        if self.login_rejected is not None:
            raise MailboxLoginRejected(self.login_rejected)
        try:
            imap = self._live_connection()
            return InboxSession(imap, imap.select_folder(INBOX))
        except Exception:
            self.drop_connection()
            raise

    def drop_connection(self) -> None:
        """Called after a failed step too, so the next poll reconnects."""
        imap, self._imap = self._imap, None
        if imap is None:
            return
        try:
            imap.logout()
        except Exception:
            pass
