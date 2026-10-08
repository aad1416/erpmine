"""Raw Mailtrap Inbound Email message JSON -> NormalizedMessage.

Mailtrap already returns decoded `text_body`/`html_body` — no MIME multipart tree to
walk, unlike Gmail's normalize.py (11-mailtrap-adapter-plan.md §1). This is a straight
field mapping, the adapter's easiest, most deterministic surface.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parseaddr
from typing import Any

from bs4 import BeautifulSoup

from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage


def _html_to_text(html: str) -> str:
    if not html.strip():
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()


def normalize_mailtrap_message(mailbox_key: MailboxKey, raw: dict[str, Any]) -> NormalizedMessage:
    sender_name, sender_address = parseaddr(raw.get("from") or "")

    return NormalizedMessage(
        adapter=mailbox_key.adapter,
        mailbox=mailbox_key.mailbox,
        # thread_id can be null (a threadless message) — fall back to the message's
        # own id so it still gets a valid conversation (implementation plan §grounding).
        conversation_id=raw.get("thread_id") or raw["id"],
        external_message_id=raw["id"],
        sender_address=sender_address,
        sender_name=sender_name or None,
        received_at=datetime.fromisoformat(raw["received_at"]),
        body_text=raw.get("text_body") or _html_to_text(raw.get("html_body") or ""),
        subject=raw.get("subject"),
        has_attachments=bool(raw.get("attachments")),
    )
