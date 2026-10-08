"""MailtrapAdapter: the dev-only Connection Method, reading Mailtrap inboxes over its
Inbound Email API.

One instance serves every Mailtrap Mailbox in `mailtrap_mailboxes`, each polled by its
own loop so one inbox failing (a rejected token, an API error) never stops the others.
There is no outbox: each new message is handed to the sink directly, and the Mailbox's
cursor (the `received_at` of the last message handed over) advances only after the sink
returns. A crash in between re-sinks the message on the next poll, which the sink
ignores as a duplicate.

Mailtrap replies to a message rather than to a thread, so the adapter keeps the newest
inbound message of each Conversation in `mailtrap_last_inbound_messages` and replies to
that one. Sent replies are recorded by idempotency key so a retried reply task sends once.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Callable

from app.db.database import SessionLocal
from app.support.adapter.base import MailboxAdapter, MessageSink, adapter
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.mailtrap.client import MailtrapClient
from app.support.adapter.mailtrap.models import (
    MailtrapLastInboundMessage,
    MailtrapMailbox,
    MailtrapSentReply,
)
from app.support.adapter.mailtrap.normalize import normalize_mailtrap_message
from app.support.adapter.mailtrap.settings import mailtrap_settings
from app.support.adapter.schemas import NormalizedMessage

logger = logging.getLogger(__name__)

ADAPTER_NAME = "mailtrap"

MailtrapClientFactory = Callable[..., MailtrapClient]


@dataclass
class _Inbox:
    """One Mailtrap Mailbox's state. `client` is None when its row lacks credentials."""

    mailbox_key: MailboxKey
    stored_address: str  # the row's primary key, as stored
    client: MailtrapClient | None
    cursor: str | None


@adapter(ADAPTER_NAME, credentials=MailtrapMailbox)
class MailtrapAdapter(MailboxAdapter):
    def __init__(
        self,
        credential_rows: list[MailtrapMailbox],
        client_factory: MailtrapClientFactory | None = None,
    ) -> None:
        client_factory = client_factory or MailtrapClient
        self._inboxes: dict[str, _Inbox] = {}
        for row in credential_rows:
            mailbox_key = MailboxKey.of(ADAPTER_NAME, row.mailbox)
            client = None
            if row.api_token and row.inbox_id:
                client = client_factory(api_token=row.api_token, inbox_id=row.inbox_id)
            self._inboxes[mailbox_key.mailbox] = _Inbox(
                mailbox_key=mailbox_key,
                stored_address=row.mailbox,
                client=client,
                cursor=row.cursor,
            )
        self._sink: MessageSink | None = None
        self._poll_tasks: list[asyncio.Task] = []

    async def start(self, sink: MessageSink) -> None:
        if self._inboxes and mailtrap_settings.DETECTION_MODE == "push":
            raise RuntimeError(
                "SUPPORT_MAILTRAP_DETECTION_MODE=push is not implemented: set it to "
                "'poll' or unset it."
            )
        self._sink = sink
        for inbox in self._inboxes.values():
            if inbox.client is None:
                logger.error(
                    "Mailtrap Mailbox %s has no API token or inbox ID: not polling it. "
                    "Run scripts/seed_support_mailboxes.py.",
                    inbox.mailbox_key.mailbox,
                )
                continue
            self._poll_tasks.append(
                asyncio.create_task(
                    self._poll_forever(inbox),
                    name=f"mailtrap-poll-{inbox.mailbox_key.mailbox}",
                )
            )
        logger.info(
            "Mailtrap polling %d Mailbox(es) every %ss",
            len(self._poll_tasks),
            mailtrap_settings.POLL_INTERVAL_SECONDS,
        )

    async def stop(self) -> None:
        for poll_task in self._poll_tasks:
            poll_task.cancel()
        for poll_task in self._poll_tasks:
            try:
                await poll_task
            except asyncio.CancelledError:
                pass
        self._poll_tasks = []

    async def send_message(
        self, mailbox: str, conversation_id: str, text: str, idempotency_key: str
    ) -> None:
        inbox = self._inboxes.get(mailbox.lower())
        if inbox is None or inbox.client is None:
            raise LookupError(f"Mailtrap: no usable Mailbox {mailbox!r} to reply from")

        db = SessionLocal()
        try:
            if db.get(MailtrapSentReply, idempotency_key) is not None:
                logger.info(
                    "Mailtrap Mailbox %s: reply %s already sent, skipping",
                    inbox.mailbox_key.mailbox,
                    idempotency_key,
                )
                return
            last_inbound = db.get(
                MailtrapLastInboundMessage, (inbox.mailbox_key.mailbox, conversation_id)
            )
            reply_to_message_id = last_inbound.external_message_id if last_inbound else None
        finally:
            db.close()

        if reply_to_message_id is None:
            raise ValueError(
                f"Mailtrap: no inbound message found for conversation_id={conversation_id!r} "
                f"in {inbox.mailbox_key.mailbox}, cannot address a reply"
            )

        await inbox.client.reply(reply_to_message_id, text)

        db = SessionLocal()
        try:
            db.add(
                MailtrapSentReply(
                    idempotency_key=idempotency_key,
                    mailbox=inbox.mailbox_key.mailbox,
                    conversation_id=conversation_id,
                )
            )
            db.commit()
        finally:
            db.close()

    async def _poll_forever(self, inbox: _Inbox) -> None:
        while True:
            try:
                await self._poll(inbox)
            except Exception:
                logger.exception("Mailtrap Mailbox %s: poll failed", inbox.mailbox_key.mailbox)
            await asyncio.sleep(mailtrap_settings.POLL_INTERVAL_SECONDS)

    async def _poll(self, inbox: _Inbox) -> None:
        # Logs carry ids, counts and timestamps only, never subject or body: inbound
        # email content is user data and this runs at INFO in dev and staging.
        if inbox.cursor is None:
            # No cursor to resume from: start from now rather than backfill the inbox's
            # whole history.
            page = await inbox.client.list_messages()
            data = page.get("data", [])
            cursor = data[0]["received_at"] if data else datetime.now(UTC).isoformat()
            self._save_cursor(inbox, cursor)
            logger.info(
                "Mailtrap Mailbox %s: seeding cursor at %s", inbox.mailbox_key.mailbox, cursor
            )
            return

        new_summaries = await self._list_since_cursor(inbox)
        if new_summaries:
            logger.info(
                "Mailtrap Mailbox %s: %d new message(s) since %s",
                inbox.mailbox_key.mailbox,
                len(new_summaries),
                inbox.cursor,
            )

        for index, summary in enumerate(new_summaries):
            raw = await inbox.client.get_message(summary["id"])
            message = normalize_mailtrap_message(inbox.mailbox_key, raw)
            # Before the sink, so the reply the worker queues for it can find it.
            self._record_last_inbound(message, summary["received_at"])
            await self._sink(message)
            # Handed over. Messages sharing a `received_at` advance the cursor together,
            # since the walk stops at the first message at or before the cursor.
            following = new_summaries[index + 1] if index + 1 < len(new_summaries) else None
            if following is None or _received_at(following) != _received_at(summary):
                self._save_cursor(inbox, summary["received_at"])

    async def _list_since_cursor(self, inbox: _Inbox) -> list[dict[str, Any]]:
        """Message summaries newer than the cursor, oldest first. Walks pages newest to
        oldest (via `last_id`) until a message at or before the cursor, or until `last_id`
        runs out at the end of Mailtrap's retention window."""
        cursor_at = datetime.fromisoformat(inbox.cursor)
        new_summaries: list[dict[str, Any]] = []
        last_id: str | None = None
        while True:
            page = await inbox.client.list_messages(last_id=last_id)
            reached_cursor = False
            for summary in page.get("data", []):
                if _received_at(summary) <= cursor_at:
                    reached_cursor = True
                    break
                new_summaries.append(summary)
            last_id = page.get("last_id")
            if reached_cursor or not last_id:
                break
        new_summaries.reverse()
        return new_summaries

    def _save_cursor(self, inbox: _Inbox, cursor: str) -> None:
        db = SessionLocal()
        try:
            db.query(MailtrapMailbox).filter(
                MailtrapMailbox.mailbox == inbox.stored_address
            ).update({MailtrapMailbox.cursor: cursor})
            db.commit()
        finally:
            db.close()
        inbox.cursor = cursor

    def _record_last_inbound(self, message: NormalizedMessage, received_at: str) -> None:
        db = SessionLocal()
        try:
            last_inbound = db.get(
                MailtrapLastInboundMessage, (message.mailbox, message.conversation_id)
            )
            if last_inbound is None:
                db.add(
                    MailtrapLastInboundMessage(
                        mailbox=message.mailbox,
                        conversation_id=message.conversation_id,
                        external_message_id=message.external_message_id,
                        received_at=received_at,
                    )
                )
            elif datetime.fromisoformat(last_inbound.received_at) <= datetime.fromisoformat(
                received_at
            ):
                last_inbound.external_message_id = message.external_message_id
                last_inbound.received_at = received_at
            db.commit()
        finally:
            db.close()


def _received_at(summary: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(summary["received_at"])
