"""Raw Mailtrap Inbound Email message JSON -> NormalizedMessage.

Mailtrap already returns decoded `text_body`/`html_body` — no MIME multipart tree to
walk, unlike Gmail's normalize.py (11-mailtrap-adapter-plan.md §1). This is a straight
field mapping, the adapter's easiest, most deterministic surface.
"""

from __future__ import annotations

import mimetypes
from datetime import datetime
from email.utils import parseaddr
from typing import Any

from app.support.adapter.attachment_candidates import AttachmentCandidate
from app.support.adapter.html_body import html_to_text
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage


def _html_to_text(html: str) -> str:
    return html_to_text(html)


def extract_mailtrap_attachment_candidates(raw: dict[str, Any]) -> list[AttachmentCandidate]:
    """Map attachments and named inline files returned by Mailtrap."""
    candidates = []
    for index, item in enumerate(raw.get("attachments", []) or []):
        disposition = str(
            item.get("disposition") or item.get("content_disposition") or "attachment"
        ).lower()
        content_type = str(
            item.get("content_type") or item.get("mime_type")
            or item.get("type")
            or mimetypes.guess_type(str(item.get("filename") or item.get("name") or ""))[0]
            or "application/octet-stream"
        )
        if disposition.startswith("inline") and not (item.get("filename") or item.get("name")):
            continue
        candidates.append(
            AttachmentCandidate(
                external_attachment_id=str(
                    item.get("attachment_id") or item.get("id") or f"attachment-{index}"
                ),
                file_name=str(item.get("filename") or item.get("name") or f"attachment-{index + 1}"),
                content_type=content_type,
                declared_size=int(item.get("size") or 0),
                download_url=item.get("download_url") or item.get("url"),
            )
        )
    return candidates


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
        has_attachments=bool(extract_mailtrap_attachment_candidates(raw)),
    )
