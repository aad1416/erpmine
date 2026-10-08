"""GmailAdapter: Mailboxes connected through the Gmail API with an OAuth refresh token
(02-architecture-decisions.md §11, §12.4). Runs beside the IMAP/SMTP adapter; each
Mailbox uses exactly one Connection Method (ADR 0002), which the Mailbox Registry checks.

One instance serves every Mailbox in `gmail_mailboxes`. Each Mailbox's state (its Gmail
client, history cursor and next watch renewal) lives in a private `_MailboxState`, and
each Mailbox is read by its own loop, so one Mailbox failing (a revoked token, a watch
error, an API error) never stops the others. Only the Gmail API calls run off the event
loop; the database work runs on it. The OAuth client ID and secret are app-wide
(`SUPPORT_GMAIL_*`, see `settings.py`); the refresh token is the Mailbox's own.

When a Mailbox is read (`SUPPORT_GMAIL_DETECTION_MODE`):
- **poll:** every POLL_INTERVAL_SECONDS.
- **push:** when the Pub/Sub webhook (`webhook.py`, served by `router()`) is notified
  for it, and every BACKUP_POLL_INTERVAL_SECONDS in case a notification was dropped. The
  same loop renews the Mailbox's users.watch() on start and every
  WATCH_RENEWAL_INTERVAL_SECONDS, well inside its 7-day expiry.

The cursor is the Gmail historyId the Mailbox has been read up to, kept on its row. A
read walks the history since the cursor, one history record at a time, and hands each
new message over through the adapter's own outbox, `gmail_outbox`:
1. in one transaction, the record's messages are written to the outbox as captured and
   the cursor moves past the record;
2. each is handed to the sink;
3. its outbox row is marked delivered.
A crash before 1 leaves the record after the cursor, so it is read again. A crash after
1 leaves undelivered rows, which are re-sunk when the adapter starts (and at the start
of each read, which also retries a sink that failed). Mail is never modified.

Our own replies (SENT and not INBOX) are skipped. With no cursor yet, or one Gmail no
longer has history for, the cursor starts from now and the gap is not backfilled (§11.2).

Replies go to the last inbound message of the thread, with In-Reply-To and References
set so Gmail keeps them in it. Each reply is recorded in `gmail_sent_replies` by its
idempotency key and carries it in a REPLY_KEY_HEADER header. A key already `sent` is
skipped. A key left `sending` (a crash, or a failed call that may still have reached
Gmail) is looked for in the thread: found, it is marked sent; not found, it is sent.
Gap: a reply Gmail filed in a different thread isn't found, so could be sent twice.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Callable

from fastapi import APIRouter
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.database import SessionLocal
from app.support.adapter.gmail.client import (
    GmailClient,
    GmailCredentialsConfig,
    HistoryExpiredError,
)
from app.support.adapter.gmail.models import (
    GmailMailbox,
    GmailOutboxMessage,
    GmailOutboxStatus,
    GmailSentReply,
    GmailSentReplyStatus,
)
from app.support.adapter.gmail.normalize import normalize_gmail_message
from app.support.adapter.gmail.settings import gmail_settings
from app.support.adapter.gmail.watch_repository import save_watch
from app.support.adapter.gmail.webhook import build_webhook_router
from app.support.adapter.base import MailboxAdapter, MessageSink, adapter
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage

logger = logging.getLogger(__name__)

ADAPTER_NAME = "gmail"

# Carries a reply's idempotency key, so a reply whose send was interrupted can be found.
REPLY_KEY_HEADER = "X-Support-Reply-Key"
_REPLY_HEADERS = ["From", "Subject", "Message-ID", "References", REPLY_KEY_HEADER]


def _added_message_ids(history_record: dict[str, Any]) -> list[str]:
    message_ids: list[str] = []
    for added in history_record.get("messagesAdded", []) or []:
        message_id = added.get("message", {}).get("id")
        if message_id and message_id not in message_ids:
            message_ids.append(message_id)
    return message_ids


def _headers(message: dict[str, Any]) -> dict[str, str]:
    """A metadata-format message's headers by lower-cased name."""
    return {
        header.get("name", "").lower(): header.get("value", "")
        for header in message.get("payload", {}).get("headers", [])
    }


def _reply_subject(subject: str | None) -> str:
    if not subject:
        return ""
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


@dataclass
class _MailboxState:
    """One Gmail Mailbox's state. `wake` is set by a push notification (and by `stop`);
    `revoked` once its refresh token is refused, which stops its reads."""

    mailbox_key: MailboxKey
    stored_address: str  # the row's primary key, as stored
    client: GmailClient
    history_id: str | None
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    next_watch_renewal: float = 0.0  # event loop time; 0 renews on the first read
    revoked: bool = False

    @property
    def address(self) -> str:
        return self.mailbox_key.mailbox


@adapter(ADAPTER_NAME, credentials=GmailMailbox)
class GmailAdapter(MailboxAdapter):
    def __init__(
        self,
        credential_rows: list[GmailMailbox],
        client_factory: Callable[..., GmailClient] | None = None,
    ) -> None:
        client_factory = client_factory or GmailClient
        self._mailboxes: dict[str, _MailboxState] = {}
        # Mailboxes in the table that this adapter doesn't serve, and why: logged at start.
        self._not_served: dict[str, str] = {}
        client_configured = bool(gmail_settings.CLIENT_ID and gmail_settings.CLIENT_SECRET)
        for row in credential_rows:
            mailbox_key = MailboxKey.of(ADAPTER_NAME, row.mailbox)
            if not client_configured:
                self._not_served[mailbox_key.mailbox] = (
                    "can't be served: SUPPORT_GMAIL_CLIENT_ID and SUPPORT_GMAIL_CLIENT_SECRET "
                    "(the app's OAuth client) are not both set"
                )
                continue
            if not row.refresh_token:
                self._not_served[mailbox_key.mailbox] = (
                    "has no refresh token. Run scripts/seed_support_mailboxes.py"
                )
                continue
            self._mailboxes[mailbox_key.mailbox] = _MailboxState(
                mailbox_key=mailbox_key,
                stored_address=row.mailbox,
                client=client_factory(
                    GmailCredentialsConfig(
                        client_id=gmail_settings.CLIENT_ID,
                        client_secret=gmail_settings.CLIENT_SECRET,
                        refresh_token=row.refresh_token,
                    ),
                    user_email=mailbox_key.mailbox,
                    timeout=gmail_settings.TIMEOUT_SECONDS,
                ),
                history_id=row.history_id,
            )
        self._sink: MessageSink | None = None
        self._stopping = asyncio.Event()
        self._read_tasks: list[asyncio.Task] = []

    def router(self) -> APIRouter:
        return build_webhook_router(self._on_push)

    async def start(self, sink: MessageSink) -> None:
        self._sink = sink
        self._stopping = asyncio.Event()
        for address, reason in self._not_served.items():
            logger.error("Gmail Mailbox %s %s: not serving it.", address, reason)
        push = gmail_settings.DETECTION_MODE == "push"
        if push and self._mailboxes and not gmail_settings.PUBSUB_TOPIC:
            logger.error(
                "Gmail push mode without SUPPORT_GMAIL_PUBSUB_TOPIC: no watch is registered, "
                "so Mailboxes are read only by the backup poll"
            )
        if push and not gmail_settings.PUBSUB_AUDIENCE:
            logger.warning(
                "Gmail push mode without SUPPORT_GMAIL_PUBSUB_AUDIENCE — webhook token "
                "verification is disabled, any caller can trigger a read"
            )
        # Messages captured before a crash first, so they reach ingestion before newer mail.
        try:
            await self._sink_undelivered()
        except Exception:
            logger.exception(
                "Gmail: re-sinking undelivered messages failed; each Mailbox's next read "
                "retries its own"
            )
        for state in self._mailboxes.values():
            state.wake = asyncio.Event()
            self._read_tasks.append(
                asyncio.create_task(self._run(state), name=f"gmail-read-{state.address}")
            )
        logger.info(
            "Gmail reading %d Mailbox(es) in %s mode every %ss",
            len(self._read_tasks),
            gmail_settings.DETECTION_MODE,
            self._read_interval(),
        )

    async def stop(self) -> None:
        """Lets each read finish the step it is on (a Gmail API request is bounded by
        the timeout), then cancels what is left."""
        self._stopping.set()
        for state in self._mailboxes.values():
            state.wake.set()
        if self._read_tasks:
            _, still_running = await asyncio.wait(
                self._read_tasks, timeout=gmail_settings.TIMEOUT_SECONDS
            )
            for read_task in still_running:
                read_task.cancel()
        self._read_tasks = []

    def _on_push(self, address: str) -> None:
        state = self._mailboxes.get(address.lower())
        if state is None:
            logger.warning("Gmail push for a Mailbox not served here: %s", address)
            return
        if state.revoked:
            logger.warning("Gmail push for %s, whose refresh token was refused", address)
            return
        state.wake.set()

    def _read_interval(self) -> float:
        if gmail_settings.DETECTION_MODE == "push":
            return gmail_settings.BACKUP_POLL_INTERVAL_SECONDS
        return gmail_settings.POLL_INTERVAL_SECONDS

    async def _run(self, state: _MailboxState) -> None:
        while not self._stopping.is_set():
            # Cleared before the read, so a push arriving during it runs another read.
            state.wake.clear()
            try:
                await self._renew_watch_if_due(state)
                await self._read(state)
            except RefreshError as error:
                state.revoked = True
                logger.error(
                    "Gmail Mailbox %s: refresh token refused (%s). Reading this Mailbox is "
                    "stopped; other Mailboxes keep running. Reconnect it: set a new refresh "
                    "token in its gmail_mailboxes row and restart.",
                    state.address,
                    error,
                )
                return
            except Exception:
                logger.exception("Gmail Mailbox %s: read failed", state.address)
            try:
                await asyncio.wait_for(state.wake.wait(), timeout=self._read_interval())
            except TimeoutError:
                pass

    async def _renew_watch_if_due(self, state: _MailboxState) -> None:
        """Push mode only. A failed renewal is retried on the Mailbox's next read; a
        refused refresh token raises."""
        topic = gmail_settings.PUBSUB_TOPIC
        if gmail_settings.DETECTION_MODE != "push" or not topic:
            return
        now = asyncio.get_running_loop().time()
        if now < state.next_watch_renewal:
            return
        try:
            response = await asyncio.to_thread(state.client.watch, topic)
            db = SessionLocal()
            try:
                save_watch(db, state.mailbox_key, response)
            finally:
                db.close()
        except RefreshError:
            raise
        except Exception:
            logger.exception(
                "Gmail Mailbox %s: watch renewal failed, retrying on its next read",
                state.address,
            )
            return
        state.next_watch_renewal = now + gmail_settings.WATCH_RENEWAL_INTERVAL_SECONDS
        logger.info("Gmail watch renewed for %s", state.address)

    async def _read(self, state: _MailboxState) -> None:
        # Logs carry IDs and counts only, never subject or body.
        await self._sink_undelivered(state.address)
        self._purge_delivered(state.address)
        db = SessionLocal()
        try:
            if state.history_id is None:
                # No cursor: start from now, nothing to backfill from before one existed.
                history_id = await asyncio.to_thread(state.client.get_current_history_id)
                self._commit_cursor(db, state, history_id)
                logger.info("Gmail Mailbox %s: seeding cursor at %s", state.address, history_id)
                return
            try:
                history_records = await asyncio.to_thread(
                    state.client.history_list, state.history_id
                )
            except HistoryExpiredError:
                expired = state.history_id
                history_id = await asyncio.to_thread(state.client.get_current_history_id)
                self._commit_cursor(db, state, history_id)
                logger.warning(
                    "Gmail Mailbox %s: historyId %s expired, resyncing from %s "
                    "(gap not backfilled, per §11.2)",
                    state.address,
                    expired,
                    history_id,
                )
                return
            previous_cursor = state.history_id
            captured_count = 0
            for history_record in history_records:
                if self._stopping.is_set():
                    break
                outbox_rows = await self._capture(db, state, history_record)
                captured_count += len(outbox_rows)
                for outbox_row in outbox_rows:
                    await self._hand_over(db, outbox_row)
            if captured_count:
                logger.info(
                    "Gmail Mailbox %s: %d new message(s), cursor %s -> %s",
                    state.address,
                    captured_count,
                    previous_cursor,
                    state.history_id,
                )
        finally:
            db.close()

    async def _capture(
        self, db: Session, state: _MailboxState, history_record: dict[str, Any]
    ) -> list[GmailOutboxMessage]:
        """Writes the record's new customer messages to the outbox and moves the cursor
        past the record, in one transaction, and returns the new outbox rows. A message
        already in the outbox (a re-read record) is not fetched again."""
        new_rows: list[GmailOutboxMessage] = []
        for message_id in _added_message_ids(history_record):
            already_captured = (
                db.query(GmailOutboxMessage.id)
                .filter_by(mailbox=state.address, external_message_id=message_id)
                .first()
            )
            if already_captured is not None:
                continue
            normalized = await self._fetch(state, message_id)
            if normalized is None:
                continue
            outbox_row = GmailOutboxMessage(
                mailbox=state.address,
                external_message_id=normalized.external_message_id,
                normalized_payload=normalized.model_dump(mode="json"),
                status=GmailOutboxStatus.captured,
            )
            db.add(outbox_row)
            new_rows.append(outbox_row)
        self._commit_cursor(db, state, history_record.get("id") or state.history_id)
        return new_rows

    async def _fetch(self, state: _MailboxState, message_id: str) -> NormalizedMessage | None:
        """The message normalized, or None when it is gone, is our own sent mail, or
        can't be normalized. Any other failure raises and fails the read, so the record
        is read again next time."""
        try:
            raw_message = await asyncio.to_thread(state.client.get_message_full, message_id)
        except HttpError as error:
            if error.resp.status == 404:
                logger.info(
                    "Gmail Mailbox %s: message %s is gone, skipping", state.address, message_id
                )
                return None
            raise
        labels = raw_message.get("labelIds", [])
        if "SENT" in labels and "INBOX" not in labels:
            logger.info(
                "Gmail Mailbox %s: skipping message %s, our own sent mail",
                state.address,
                message_id,
            )
            return None
        try:
            return normalize_gmail_message(state.mailbox_key, raw_message)
        except Exception:
            logger.error(
                "Gmail Mailbox %s: message %s can't be normalized, skipping it",
                state.address,
                message_id,
                exc_info=True,
            )
            return None

    async def _hand_over(self, db: Session, outbox_row: GmailOutboxMessage) -> None:
        await self._sink(NormalizedMessage.model_validate(outbox_row.normalized_payload))
        outbox_row.status = GmailOutboxStatus.delivered
        outbox_row.delivered_at = datetime.now(UTC)
        db.commit()

    async def _sink_undelivered(self, mailbox: str | None = None) -> None:
        """Hands over every captured-but-undelivered message, oldest first: of `mailbox`,
        or of every Mailbox. A sink failure raises and leaves the rest for next time."""
        db = SessionLocal()
        try:
            query = db.query(GmailOutboxMessage).filter_by(status=GmailOutboxStatus.captured)
            if mailbox is not None:
                query = query.filter_by(mailbox=mailbox)
            undelivered = query.order_by(GmailOutboxMessage.id).all()
            if undelivered:
                logger.info(
                    "Gmail: re-sinking %d undelivered message(s) of %s",
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
            db.query(GmailOutboxMessage).filter(
                GmailOutboxMessage.mailbox == mailbox,
                GmailOutboxMessage.status == GmailOutboxStatus.delivered,
                GmailOutboxMessage.delivered_at < cutoff,
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def _commit_cursor(self, db: Session, state: _MailboxState, history_id: str) -> None:
        """Saves the cursor with whatever else `db` holds, in one transaction."""
        db.query(GmailMailbox).filter(GmailMailbox.mailbox == state.stored_address).update(
            {GmailMailbox.history_id: history_id}
        )
        db.commit()
        state.history_id = history_id

    async def send_message(
        self, mailbox: str, conversation_id: str, text: str, idempotency_key: str
    ) -> None:
        """Reply to the thread's last inbound sender only (no reply-all). A reply already
        sent under `idempotency_key` is skipped. A Gmail API failure raises, so the send
        task goes to retry and dead-letter, and the retry looks for the reply in the
        thread before sending it."""
        state = self._mailboxes.get(mailbox.lower())
        if state is None:
            raise LookupError(f"Gmail: no usable Mailbox {mailbox!r} to reply from")

        db = SessionLocal()
        try:
            sent_reply, interrupted = self._claim_send(db, state, conversation_id, idempotency_key)
            if sent_reply is None:
                return
            thread = await asyncio.to_thread(
                state.client.get_thread_metadata, conversation_id, _REPLY_HEADERS
            )
            if interrupted and self._reply_in_thread(thread, idempotency_key):
                logger.info(
                    "Gmail Mailbox %s: reply %s was sent before an interruption, found in "
                    "its thread; not sending it again",
                    state.address,
                    idempotency_key,
                )
            else:
                reply = self._build_reply(state, thread, text, idempotency_key)
                # On failure the row stays `sending`, so the retry checks the thread first.
                await asyncio.to_thread(state.client.send_message, reply, conversation_id)
                logger.info(
                    "Gmail Mailbox %s: sent reply %s in conversation %s",
                    state.address,
                    idempotency_key,
                    conversation_id,
                )
            sent_reply.status = GmailSentReplyStatus.sent
            sent_reply.sent_at = datetime.now(UTC)
            db.commit()
        finally:
            db.close()

    def _claim_send(
        self, db: Session, state: _MailboxState, conversation_id: str, idempotency_key: str
    ) -> tuple[GmailSentReply | None, bool]:
        """Records the reply as `sending` and returns (row, False); returns (row, True)
        for a `sending` row an earlier attempt left, whose reply may or may not have
        reached Gmail; or (None, False) when the key was already sent."""
        existing = db.get(GmailSentReply, idempotency_key)
        if existing is None:
            sent_reply = GmailSentReply(
                idempotency_key=idempotency_key,
                mailbox=state.address,
                conversation_id=conversation_id,
                status=GmailSentReplyStatus.sending,
            )
            db.add(sent_reply)
            try:
                db.commit()
                return sent_reply, False
            except IntegrityError:
                db.rollback()
                existing = db.get(GmailSentReply, idempotency_key)
        if existing.status == GmailSentReplyStatus.sent:
            logger.info(
                "Gmail Mailbox %s: reply %s already sent, skipping", state.address, idempotency_key
            )
            return None, False
        logger.warning(
            "Gmail Mailbox %s: reply %s was being sent when a previous attempt stopped; "
            "looking for it in its thread before sending",
            state.address,
            idempotency_key,
        )
        return existing, True

    @staticmethod
    def _reply_in_thread(thread: dict[str, Any], idempotency_key: str) -> bool:
        return any(
            "SENT" in message.get("labelIds", [])
            and _headers(message).get(REPLY_KEY_HEADER.lower()) == idempotency_key
            for message in thread.get("messages", [])
        )

    @staticmethod
    def _build_reply(
        state: _MailboxState, thread: dict[str, Any], text: str, idempotency_key: str
    ) -> EmailMessage:
        """Addressed to the last inbound (INBOX) message's sender, walking back so a bot
        reply never becomes the target; the last message if none is inbound."""
        messages = thread["messages"]
        parent = next(
            (message for message in reversed(messages) if "INBOX" in message.get("labelIds", [])),
            messages[-1],
        )
        parent_headers = _headers(parent)
        _, to_address = parseaddr(parent_headers.get("from", ""))
        references = parent_headers.get("references", "").split()
        parent_message_id = parent_headers.get("message-id")
        if parent_message_id:
            references.append(parent_message_id)

        reply = EmailMessage()
        reply["From"] = state.address
        reply["To"] = to_address
        reply["Subject"] = _reply_subject(parent_headers.get("subject"))
        if parent_message_id:
            reply["In-Reply-To"] = parent_message_id
        if references:
            reply["References"] = " ".join(references)
        reply[REPLY_KEY_HEADER] = idempotency_key
        reply.set_content(text)
        return reply
