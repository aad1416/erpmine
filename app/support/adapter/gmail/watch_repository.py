"""Stores each push-mode Mailbox's users.watch() registration in `gmail_watches`."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy.orm import Session

from app.support.adapter.gmail.models import GmailWatch
from app.support.adapter.mailbox_key import MailboxKey


def save_watch(db: Session, mailbox_key: MailboxKey, watch_response: dict[str, Any]) -> None:
    """Records the historyId and expiry from a users.watch() response, and commits."""
    expiration_ms = int(watch_response["expiration"])
    row = db.get(GmailWatch, (mailbox_key.adapter, mailbox_key.mailbox))
    if row is None:
        row = GmailWatch(adapter=mailbox_key.adapter, mailbox=mailbox_key.mailbox)
        db.add(row)
    row.history_id = watch_response.get("historyId")
    row.watch_expiration = datetime.fromtimestamp(expiration_ms / 1000, tz=UTC)
    db.commit()
