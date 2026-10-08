"""ImapAdapter: Mailboxes connected over IMAP with an app password (ADR 0002). Runs
beside the Gmail API adapter; each Mailbox uses exactly one Connection Method, which the
Mailbox Registry checks.

One instance serves every Mailbox in `imap_mailboxes`. Each Mailbox's state (its IMAP
client, SMTP sender, cursor, and the client's login-rejected flag) lives in a private
`_MailboxState`, and each Mailbox is polled by its own loop, so one Mailbox failing (a
rejected app password, a hung server, a changed UIDVALIDITY) never stops the others.
Only the IMAP calls run off the event loop; the database work runs on it.

The cursor is `"<uidvalidity>:<last_uid>"` over INBOX, kept on the Mailbox's row. Each
new message is read with BODY.PEEK and handed over through IMAP's own outbox,
`imap_outbox`:
1. in one transaction, the message is written to the outbox as captured and the cursor
   moves past it;
2. it is marked read on the server;
3. it is handed to the sink;
4. its outbox row is marked delivered.
A crash before 1 leaves the message unread and before the cursor, so it is fetched again.
A crash after 1 leaves an undelivered row, which is re-sunk when the adapter starts (and
at the start of each poll, which also retries a sink that failed). Mail is never moved or
deleted.

Replies go out over SMTP (`smtp.py`), threaded from `imap_thread_messages`: the fetch
path records every inbound message there before capturing it, and `send_message`
records its generated Message-ID before sending, so our own reply is recognised and
skipped if it ever comes back in through INBOX. Other non-customer mail (drafts, sent
mail, mail from the Mailbox itself, auto-replies, bounces; see `filters.py`) is skipped
the same way: marked read, never captured, and the cursor moves past it. Each reply is
recorded in `imap_sent_replies` by its idempotency key, so a retried reply task sends
once.

A Mailbox keeps running through failures: at most MAX_MESSAGES_PER_POLL messages per
poll; oversized messages and a message that fails MAX_ATTEMPTS polls running are logged
and skipped; a UIDVALIDITY change rescans the last RESCAN_DAYS by date; a rejected login
stops polling this Mailbox only. A hung IMAP step times out in the client.

Any Mail Provider works. When the server offers Gmail's X-GM-EXT-1 extension, message
and Conversation IDs are Gmail's own (equal to the Gmail API's). Otherwise they come from
standard headers (`_ids`): the message ID is the Message-ID header, and Conversations are
linked by In-Reply-To/References through `imap_thread_messages`.
"""

from __future__ import annotations

import asyncio
import imaplib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Callable

from aiosmtplib import send as aiosmtplib_send
from fastapi import APIRouter
from imapclient import IMAPClient
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.database import SessionLocal
from app.support.adapter.imap.accounts import ImapMailboxConfig
from app.support.adapter.imap.client import (
    FetchedMessage,
    ImapMailboxClient,
    InboxSession,
    MailboxLoginRejected,
    PasswordAuthenticator,
)
from app.support.adapter.imap.filters import SkipReason, non_customer_reason
from app.support.adapter.imap.models import (
    ImapMailbox,
    ImapOutboxMessage,
    ImapOutboxStatus,
    ImapSentReply,
    ImapSentReplyStatus,
)
from app.support.adapter.imap.normalize import (
    ThreadHeaders,
    gmail_id_hex,
    header_message_key,
    new_conversation_id,
    normalize_imap_message,
    read_thread_headers,
)
from app.support.adapter.imap.settings import imap_settings
from app.support.adapter.imap.smtp import (
    SmtpMailboxSender,
    SmtpSend,
    build_reply,
    new_message_id,
    reply_subject,
)
from app.support.adapter.imap.thread_repository import ImapThreadRepository
from app.support.adapter.base import MailboxAdapter, MessageSink, adapter
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage

logger = logging.getLogger(__name__)

ADAPTER_NAME = "imap"

MAX_MESSAGES_PER_POLL = 200  # the rest wait for the next poll, oldest first
MAX_MESSAGE_BYTES = 25 * 1024 * 1024  # larger messages are logged and skipped
MAX_ATTEMPTS = 3  # a message that fails this many polls running is logged and skipped
RESCAN_DAYS = 3  # how far back to rescan by date after a UIDVALIDITY change

# Failures of the connection or the database, not of one message: they fail the whole
# poll (the next poll retries it) and never count toward a message's attempts.
_INFRASTRUCTURE_ERRORS = (OSError, imaplib.IMAP4.error, OperationalError, InterfaceError)


@dataclass(frozen=True)
class ImapCursor:
    """`"<uidvalidity>:<last_uid>"`, or `"<uidvalidity>:<last_uid>:<failing_uid>:<failures>"`
    while the message after the cursor keeps failing. Keeping the failure count in the
    cursor means it is saved with the cursor and survives a restart."""

    uidvalidity: int
    last_uid: int
    failing_uid: int | None = None
    failures: int = 0

    @classmethod
    def parse(cls, value: str) -> "ImapCursor":
        uidvalidity, last_uid, *failure = (int(part) for part in value.split(":"))
        if failure:
            return cls(uidvalidity, last_uid, failure[0], failure[1])
        return cls(uidvalidity, last_uid)

    def __str__(self) -> str:
        if self.failing_uid is None:
            return f"{self.uidvalidity}:{self.last_uid}"
        return f"{self.uidvalidity}:{self.last_uid}:{self.failing_uid}:{self.failures}"


@dataclass
class _MailboxState:
    """One IMAP Mailbox's state. `client.login_rejected` is set once its login fails."""

    mailbox_key: MailboxKey
    stored_address: str  # the row's primary key, as stored
    config: ImapMailboxConfig
    client: ImapMailboxClient
    smtp: SmtpMailboxSender
    cursor: str | None

    @property
    def address(self) -> str:
        return self.mailbox_key.mailbox


@adapter(ADAPTER_NAME, credentials=ImapMailbox)
class ImapAdapter(MailboxAdapter):
    def router(self) -> APIRouter:
        from app.support.adapter.imap.routes import router

        return router

    def __init__(
        self,
        credential_rows: list[ImapMailbox],
        imap_factory: Callable[..., IMAPClient] | None = None,
        smtp_send: SmtpSend | None = None,
    ) -> None:
        imap_factory = imap_factory or IMAPClient
        smtp_send = smtp_send or aiosmtplib_send
        self._mailboxes: dict[str, _MailboxState] = {}
        # Mailboxes in the table that this adapter doesn't serve, and why: logged at start.
        self._not_served: dict[str, str] = {}
        for row in credential_rows:
            mailbox_key = MailboxKey.of(ADAPTER_NAME, row.mailbox)
            if not row.app_password:
                self._not_served[mailbox_key.mailbox] = (
                    "has no app password. Run scripts/seed_support_mailboxes.py"
                )
                continue
            config = ImapMailboxConfig(
                email=mailbox_key.mailbox,
                app_password=row.app_password,
                imap_host=row.imap_host,
                imap_port=row.imap_port,
                imap_tls_mode=row.imap_tls_mode,
                smtp_host=row.smtp_host,
                smtp_port=row.smtp_port,
                smtp_tls_mode=row.smtp_tls_mode,
            )
            self._mailboxes[mailbox_key.mailbox] = _MailboxState(
                mailbox_key=mailbox_key,
                stored_address=row.mailbox,
                config=config,
                client=ImapMailboxClient(
                    host=config.imap_host,
                    port=config.imap_port,
                    tls_mode=config.imap_tls_mode,
                    authenticator=PasswordAuthenticator(config.email, config.app_password),
                    timeout=imap_settings.TIMEOUT_SECONDS,
                    imap_factory=imap_factory,
                ),
                smtp=SmtpMailboxSender(
                    config, timeout=imap_settings.TIMEOUT_SECONDS, smtp_send=smtp_send
                ),
                cursor=row.cursor,
            )
        self._sink: MessageSink | None = None
        self._stopping = asyncio.Event()
        self._poll_tasks: list[asyncio.Task] = []

    async def start(self, sink: MessageSink) -> None:
        self._sink = sink
        self._stopping = asyncio.Event()
        for address, reason in self._not_served.items():
            logger.error("IMAP Mailbox %s %s: not serving it.", address, reason)
        # Messages captured before a crash first, so they reach ingestion before newer mail.
        try:
            await self._sink_undelivered()
        except Exception:
            logger.exception(
                "IMAP: re-sinking undelivered messages failed; each Mailbox's next poll "
                "retries its own"
            )
        for state in self._mailboxes.values():
            self._poll_tasks.append(
                asyncio.create_task(self._poll_forever(state), name=f"imap-poll-{state.address}")
            )
        logger.info(
            "IMAP polling %d Mailbox(es) every %ss",
            len(self._poll_tasks),
            imap_settings.POLL_INTERVAL_SECONDS,
        )

    async def stop(self) -> None:
        """Lets each poll finish the step it is on (an IMAP step is bounded by the
        timeout), then drops the connections."""
        self._stopping.set()
        if self._poll_tasks:
            _, still_running = await asyncio.wait(
                self._poll_tasks, timeout=imap_settings.TIMEOUT_SECONDS
            )
            for poll_task in still_running:
                poll_task.cancel()
        self._poll_tasks = []
        for state in self._mailboxes.values():
            await asyncio.to_thread(state.client.drop_connection)

    async def send_message(
        self, mailbox: str, conversation_id: str, text: str, idempotency_key: str
    ) -> None:
        """Reply to the Conversation's last inbound sender only (no reply-all). A reply
        already sent under `idempotency_key` is skipped. An SMTP failure raises, so the
        send task goes to retry and dead-letter, and the retry sends it."""
        state = self._mailboxes.get(mailbox.lower())
        if state is None:
            raise LookupError(f"IMAP: no usable Mailbox {mailbox!r} to reply from")

        db = SessionLocal()
        try:
            sent_reply = self._claim_send(db, state, conversation_id, idempotency_key)
            if sent_reply is None:
                return
            try:
                reply, recipient = self._prepare_reply(db, state, sent_reply, text)
                await state.smtp.send(reply, recipient)
            except Exception:
                # Nothing reached the customer as far as we know: release the key so
                # the retry sends.
                db.rollback()
                db.query(ImapSentReply).filter_by(idempotency_key=idempotency_key).delete()
                db.commit()
                raise
            sent_reply.status = ImapSentReplyStatus.sent
            sent_reply.sent_at = datetime.now(UTC)
            db.commit()
        finally:
            db.close()
        logger.info(
            "IMAP Mailbox %s: sent reply %s in conversation %s",
            state.address,
            reply["Message-ID"],
            conversation_id,
        )

    def _claim_send(
        self, db: Session, state: _MailboxState, conversation_id: str, idempotency_key: str
    ) -> ImapSentReply | None:
        """Records the reply as `sending`, or returns None if this key was used before.

        A `sending` row that is still there means an earlier attempt stopped between
        SMTP and recording the result (a crash, or the worker cancelled mid-send), so
        the reply may or may not have reached the customer. It is not sent again: a
        missing reply is logged, a duplicate would reach the customer."""
        existing = db.get(ImapSentReply, idempotency_key)
        if existing is None:
            sent_reply = ImapSentReply(
                idempotency_key=idempotency_key,
                mailbox=state.address,
                conversation_id=conversation_id,
                status=ImapSentReplyStatus.sending,
            )
            db.add(sent_reply)
            try:
                db.commit()
                return sent_reply
            except IntegrityError:
                db.rollback()
                existing = db.get(ImapSentReply, idempotency_key)
        if existing.status == ImapSentReplyStatus.sent:
            logger.info(
                "IMAP Mailbox %s: reply %s already sent, skipping", state.address, idempotency_key
            )
        else:
            logger.warning(
                "IMAP Mailbox %s: reply %s (Message-ID %s) was being sent when a previous "
                "attempt stopped, so it may or may not have reached the customer. Not "
                "sending it again; check the Mailbox's Sent folder.",
                state.address,
                idempotency_key,
                existing.message_id or "not yet built",
            )
        return None

    def _prepare_reply(
        self, db: Session, state: _MailboxState, sent_reply: ImapSentReply, text: str
    ) -> tuple[EmailMessage, str]:
        """Build the reply and record its Message-ID before it is sent: if SMTP accepts
        it but we crash or time out before hearing back, the ID is already known and the
        fetch path still skips the reply when it comes back in."""
        conversation_id = sent_reply.conversation_id
        thread_repo = ImapThreadRepository(db)
        parent = thread_repo.last_inbound(state.mailbox_key, conversation_id)
        if parent is None:
            raise LookupError(
                f"IMAP Mailbox {state.address}: no inbound message recorded for "
                f"conversation {conversation_id!r}, cannot address a reply"
            )
        references = (parent.reference_ids or "").split()
        if parent.message_id:
            references.append(parent.message_id)
        message_id = new_message_id(state.config.email)
        subject = reply_subject(parent.subject)
        sent_at = datetime.now(UTC)

        sent_reply.message_id = message_id  # committed with the thread record below
        thread_repo.record_outbound(
            state.mailbox_key,
            conversation_id,
            message_id=message_id,
            references=references,
            sender_address=state.config.email,
            subject=subject,
            sent_at=sent_at,
        )
        reply = build_reply(
            from_address=state.config.email,
            to_address=parent.sender_address,
            subject=subject,
            body_text=text,
            message_id=message_id,
            in_reply_to=parent.message_id,
            references=references,
            sent_at=sent_at,
        )
        return reply, parent.sender_address

    async def _poll_forever(self, state: _MailboxState) -> None:
        while not self._stopping.is_set():
            try:
                await self._poll(state)
            except MailboxLoginRejected as error:
                logger.error(
                    "IMAP Mailbox %s: login rejected (%s). Polling of this Mailbox is "
                    "stopped; other Mailboxes keep running. If the Google account's "
                    "password changed, its app password was revoked: set a new one in its "
                    "imap_mailboxes row and restart.",
                    state.address,
                    error,
                )
                return
            except Exception:
                logger.exception("IMAP Mailbox %s: poll failed", state.address)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=imap_settings.POLL_INTERVAL_SECONDS
                )
            except TimeoutError:
                pass

    async def _poll(self, state: _MailboxState) -> None:
        await self._sink_undelivered(state.address)
        self._purge_delivered(state.address)
        inbox = await asyncio.to_thread(state.client.open_inbox)
        db = SessionLocal()
        try:
            await self._read_inbox(db, state, inbox)
        except Exception:
            await asyncio.to_thread(state.client.drop_connection)
            raise
        finally:
            db.close()

    async def _read_inbox(self, db: Session, state: _MailboxState, inbox: InboxSession) -> None:
        # Logs carry IDs and counts only, never subject or body.
        if state.cursor is None:
            # No cursor: start from now, no backfill, the same stance as Gmail's.
            position = ImapCursor(inbox.uidvalidity, inbox.uidnext - 1)
            self._commit_cursor(db, state, position)
            logger.info("IMAP Mailbox %s: seeding cursor at %s", state.address, position)
            return

        previous_cursor = state.cursor
        position = ImapCursor.parse(state.cursor)
        if position.uidvalidity != inbox.uidvalidity:
            position = await self._rescan_start(state, inbox, position)

        uids = await asyncio.to_thread(inbox.uids_after, position.last_uid, MAX_MESSAGES_PER_POLL)
        position = await self._ingest(db, state, inbox, uids, position)
        if str(position) != state.cursor:
            self._commit_cursor(db, state, position)
        if uids:
            logger.info(
                "IMAP Mailbox %s: %d new message(s), cursor %s -> %s",
                state.address,
                len(uids),
                previous_cursor,
                state.cursor,
            )

    async def _rescan_start(
        self, state: _MailboxState, inbox: InboxSession, old: ImapCursor
    ) -> ImapCursor:
        """Old UIDs mean nothing under a new UIDVALIDITY, so restart just before the first
        message of the last RESCAN_DAYS. Mail already handed over is not handed over
        again: its outbox row (kept SUPPORT_RETENTION_DAYS) is found by message ID, and
        message IDs (Gmail's, or from the headers) don't change."""
        since = (datetime.now(UTC) - timedelta(days=RESCAN_DAYS)).date()
        first_uid = await asyncio.to_thread(inbox.first_uid_since, since)
        start = ImapCursor(
            inbox.uidvalidity, first_uid - 1 if first_uid is not None else inbox.uidnext - 1
        )
        logger.warning(
            "IMAP Mailbox %s: UIDVALIDITY changed %s -> %s, rescanning mail since %s "
            "(restarting at %s)",
            state.address,
            old.uidvalidity,
            inbox.uidvalidity,
            since.isoformat(),
            start,
        )
        return start

    async def _ingest(
        self,
        db: Session,
        state: _MailboxState,
        inbox: InboxSession,
        uids: list[int],
        position: ImapCursor,
    ) -> ImapCursor:
        """Hand over `uids` in order and return the cursor to save. A message that fails
        stops the poll there, so it is retried first next poll; on its MAX_ATTEMPTS-th
        failure it is skipped instead. Oversized and failed messages are left unread, so
        a person looking at the Mailbox still sees them. Skipped messages don't save the
        cursor themselves: the next capture or the end of the poll does."""
        sizes = await asyncio.to_thread(inbox.sizes, uids)
        last_uid = position.last_uid
        for uid in uids:
            if self._stopping.is_set():
                break
            size = sizes.get(uid)
            if size is not None and size > MAX_MESSAGE_BYTES:
                logger.warning(
                    "IMAP Mailbox %s: skipping UID %s, %d bytes is over the %d byte limit "
                    "(left unread)",
                    state.address,
                    uid,
                    size,
                    MAX_MESSAGE_BYTES,
                )
            elif size is not None:
                try:
                    outbox_row = await self._capture(db, state, inbox, uid)
                except _INFRASTRUCTURE_ERRORS:
                    raise
                except Exception as error:
                    db.rollback()
                    attempts = (position.failures if position.failing_uid == uid else 0) + 1
                    if attempts < MAX_ATTEMPTS:
                        logger.warning(
                            "IMAP Mailbox %s: UID %s failed (attempt %d of %d), retrying "
                            "next poll: %s",
                            state.address,
                            uid,
                            attempts,
                            MAX_ATTEMPTS,
                            type(error).__name__,
                        )
                        return ImapCursor(inbox.uidvalidity, last_uid, uid, attempts)
                    logger.error(
                        "IMAP Mailbox %s: UID %s failed %d times, skipping it (left unread)",
                        state.address,
                        uid,
                        attempts,
                        exc_info=True,
                    )
                else:
                    if outbox_row is not None:
                        await asyncio.to_thread(inbox.mark_read, uid)
                        if outbox_row.status == ImapOutboxStatus.captured:
                            await self._hand_over(db, outbox_row)
            # size None: expunged since the search, nothing to capture.
            last_uid = uid
        return ImapCursor(inbox.uidvalidity, last_uid)

    async def _capture(
        self, db: Session, state: _MailboxState, inbox: InboxSession, uid: int
    ) -> ImapOutboxMessage | None:
        """Writes the message to the outbox and moves the cursor past it, in one
        transaction, and returns its outbox row. A re-fetched message returns its
        existing row. Non-customer mail is marked read and returns None."""
        message = await asyncio.to_thread(inbox.fetch, uid)
        if message is None:
            return None
        headers = read_thread_headers(message.raw)
        thread_repo = ImapThreadRepository(db)
        if thread_repo.is_sent_by_us(state.mailbox_key, headers.message_id):
            logger.info(
                "IMAP Mailbox %s: skipping UID %s, our own sent reply", state.address, uid
            )
            await asyncio.to_thread(inbox.mark_read, uid)
            return None
        skip = non_customer_reason(message.raw, message.labels, state.config.email)
        if skip is not None:
            self._log_skip(state, uid, skip)
            await asyncio.to_thread(inbox.mark_read, uid)
            return None
        external_message_id, conversation_id = self._ids(state, message, headers, thread_repo)
        normalized = normalize_imap_message(
            state.mailbox_key,
            message.raw,
            external_message_id=external_message_id,
            conversation_id=conversation_id,
            received_at=message.internal_date,
        )
        thread_repo.record_inbound(
            state.mailbox_key,
            normalized.conversation_id,
            headers,
            sender_address=normalized.sender_address,
            subject=normalized.subject,
            received_at=normalized.received_at,
        )

        outbox_row = (
            db.query(ImapOutboxMessage)
            .filter_by(mailbox=state.address, external_message_id=external_message_id)
            .one_or_none()
        )
        if outbox_row is None:
            outbox_row = ImapOutboxMessage(
                mailbox=state.address,
                external_message_id=external_message_id,
                normalized_payload=normalized.model_dump(mode="json"),
                status=ImapOutboxStatus.captured,
            )
            db.add(outbox_row)
        self._commit_cursor(db, state, ImapCursor(inbox.uidvalidity, uid))
        return outbox_row

    def _ids(
        self,
        state: _MailboxState,
        message: FetchedMessage,
        headers: ThreadHeaders,
        thread_repo: ImapThreadRepository,
    ) -> tuple[str, str]:
        """(external message ID, Conversation ID). Gmail's IDs when the server has them.
        Otherwise from headers: the message joins the Conversation of the message it
        answers (In-Reply-To, then References newest first) when that is in the threading
        table, inbound or ours; else it starts a new one. Never matched by subject."""
        if message.gm_msgid is not None:
            return gmail_id_hex(message.gm_msgid), gmail_id_hex(message.gm_thrid)
        external_message_id = header_message_key(message.raw, headers)
        linked = [*headers.in_reply_to, *reversed(headers.references)]
        if headers.message_id is not None:
            linked.insert(0, headers.message_id)  # already recorded: a re-fetch
        conversation_id = thread_repo.conversation_of(state.mailbox_key, linked)
        return external_message_id, conversation_id or new_conversation_id(external_message_id)

    def _log_skip(self, state: _MailboxState, uid: int, skip: SkipReason) -> None:
        if skip.kind == "bounce":
            logger.warning(
                "IMAP Mailbox %s: skipping UID %s, bounce of message %s",
                state.address,
                uid,
                skip.original_message_id or "(unknown Message-ID)",
            )
        else:
            logger.info("IMAP Mailbox %s: skipping UID %s, %s", state.address, uid, skip.kind)

    async def _hand_over(self, db: Session, outbox_row: ImapOutboxMessage) -> None:
        await self._sink(NormalizedMessage.model_validate(outbox_row.normalized_payload))
        outbox_row.status = ImapOutboxStatus.delivered
        outbox_row.delivered_at = datetime.now(UTC)
        db.commit()

    async def _sink_undelivered(self, mailbox: str | None = None) -> None:
        """Hands over every captured-but-undelivered message, oldest first: of `mailbox`,
        or of every Mailbox. A sink failure raises and leaves the rest for next time."""
        db = SessionLocal()
        try:
            query = db.query(ImapOutboxMessage).filter_by(status=ImapOutboxStatus.captured)
            if mailbox is not None:
                query = query.filter_by(mailbox=mailbox)
            undelivered = query.order_by(ImapOutboxMessage.id).all()
            if undelivered:
                logger.info(
                    "IMAP: re-sinking %d undelivered message(s) of %s",
                    len(undelivered),
                    mailbox or "every Mailbox",
                )
            for outbox_row in undelivered:
                await self._hand_over(db, outbox_row)
        finally:
            db.close()

    def _purge_delivered(self, mailbox: str) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=settings.SUPPORT_RETENTION_DAYS)
        db = SessionLocal()
        try:
            db.query(ImapOutboxMessage).filter(
                ImapOutboxMessage.mailbox == mailbox,
                ImapOutboxMessage.status == ImapOutboxStatus.delivered,
                ImapOutboxMessage.delivered_at < cutoff,
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _commit_cursor(self, db: Session, state: _MailboxState, position: ImapCursor) -> None:
        """Saves the cursor with whatever else `db` holds, in one transaction."""
        db.query(ImapMailbox).filter(ImapMailbox.mailbox == state.stored_address).update(
            {ImapMailbox.cursor: str(position)}
        )
        db.commit()
        state.cursor = str(position)
