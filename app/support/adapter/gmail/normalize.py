"""Raw Gmail `full`-format message -> NormalizedMessage (02-architecture-decisions.md §12.4).

This is the component most likely to break on real-world mail shapes — see the dedicated
MIME fixture set in tests/support/adapter/gmail/test_normalize.py.
"""

from __future__ import annotations

import base64
from datetime import datetime, UTC
from typing import Any

from bs4 import BeautifulSoup

from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage


def _header(headers: list[dict[str, str]], name: str) -> str | None:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")
    return None


def _decode_part_body(data: str | None) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _walk_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the MIME part tree (payload itself may or may not have `parts`)."""
    parts = [payload]
    for part in payload.get("parts", []) or []:
        parts.extend(_walk_parts(part))
    return parts


def _extract_body_text(payload: dict[str, Any]) -> str:
    parts = _walk_parts(payload)

    for part in parts:
        if part.get("mimeType") == "text/plain":
            text = _decode_part_body(part.get("body", {}).get("data"))
            if text.strip():
                return text

    for part in parts:
        if part.get("mimeType") == "text/html":
            html = _decode_part_body(part.get("body", {}).get("data"))
            if html.strip():
                return BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()

    return ""


def _has_attachments(payload: dict[str, Any]) -> bool:
    for part in _walk_parts(payload):
        filename = part.get("filename")
        if filename:
            return True
    return False


def normalize_gmail_message(
    mailbox_key: MailboxKey, raw_message: dict[str, Any]
) -> NormalizedMessage:
    payload = raw_message.get("payload", {})
    headers = payload.get("headers", [])

    from_header = _header(headers, "From") or ""
    sender_address = from_header
    sender_name: str | None = None
    if "<" in from_header and ">" in from_header:
        sender_name = from_header.split("<")[0].strip().strip('"') or None
        sender_address = from_header.split("<")[1].split(">")[0].strip()

    internal_date_ms = int(raw_message.get("internalDate", "0"))
    received_at = datetime.fromtimestamp(internal_date_ms / 1000, tz=UTC)

    return NormalizedMessage(
        adapter=mailbox_key.adapter,
        mailbox=mailbox_key.mailbox,
        conversation_id=raw_message["threadId"],
        external_message_id=raw_message["id"],
        sender_address=sender_address,
        sender_name=sender_name,
        received_at=received_at,
        body_text=_extract_body_text(payload),
        subject=_header(headers, "Subject"),
        has_attachments=_has_attachments(payload),
    )
