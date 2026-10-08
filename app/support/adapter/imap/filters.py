"""Which fetched mail is not from a customer and must never feed a Conversation.

The Mailbox is used only by this app, so anything Gmail labels `\\Sent` or that comes
from the Mailbox's own address is ours. Drafts, auto-replies and bounces are skipped
too, so the AI never answers a machine and replies can't loop. The From-address,
auto-reply and bounce checks read headers only, so they also work on servers without
Gmail labels.
"""

from __future__ import annotations

import email
import email.policy
from dataclasses import dataclass
from email.message import EmailMessage

from app.support.adapter.imap.normalize import message_ids, sender

SENT_LABEL = "\\Sent"
DRAFT_LABEL = "\\Draft"

_AUTO_REPLY_PRECEDENCE = {"bulk", "auto_reply", "junk"}
_BOUNCE_SENDERS = {"mailer-daemon", "postmaster"}


@dataclass(frozen=True)
class SkipReason:
    kind: str  # "draft" | "sent" | "from_mailbox" | "bounce" | "auto_reply"
    # Bounces only: the Message-ID of the mail that bounced, when the report carries it.
    original_message_id: str | None = None


def _header(message: EmailMessage, name: str) -> str | None:
    value = message.get(name)
    return None if value is None else str(value).strip()


def _is_delivery_status_report(message: EmailMessage) -> bool:
    if message.get_content_type() == "multipart/report" and (
        (message.get_param("report-type") or "").lower() == "delivery-status"
    ):
        return True
    return any(part.get_content_type() == "message/delivery-status" for part in message.walk())


def _is_bounce(message: EmailMessage) -> bool:
    return_path = _header(message, "Return-Path")
    if return_path is not None and return_path.strip("<> ") == "":
        return True
    local_part = sender(message)[1].partition("@")[0].lower()
    if local_part in _BOUNCE_SENDERS:
        return True
    return _is_delivery_status_report(message)


def _bounced_message_id(message: EmailMessage) -> str | None:
    """The bounced mail's Message-ID, from the report's returned message or headers,
    falling back to the bounce's own In-Reply-To."""
    for part in message.walk():
        content_type = part.get_content_type()
        if content_type == "message/rfc822":
            payload = part.get_payload()
            original = payload[0] if isinstance(payload, list) and payload else None
        elif content_type == "text/rfc822-headers":
            original = email.message_from_string(
                part.get_payload(decode=True).decode("utf-8", errors="replace"),
                policy=email.policy.default,
            )
        else:
            continue
        if original is not None:
            ids = message_ids(original.get("Message-ID"))
            if ids:
                return ids[0]
    ids = message_ids(message.get("In-Reply-To"))
    return ids[0] if ids else None


def _is_auto_reply(message: EmailMessage) -> bool:
    auto_submitted = _header(message, "Auto-Submitted")
    if auto_submitted is not None and auto_submitted.split(";")[0].strip().lower() != "no":
        return True
    if message.get("X-Autoreply") is not None:
        return True
    precedence = (_header(message, "Precedence") or "").lower()
    return precedence in _AUTO_REPLY_PRECEDENCE


def non_customer_reason(raw: bytes, labels: frozenset[str], mailbox_email: str) -> SkipReason | None:
    """Why this message is not customer mail, or None if it is. Bounces are checked
    before auto-replies: many carry `Auto-Submitted` too, and bounces are logged."""
    if DRAFT_LABEL in labels:
        return SkipReason("draft")
    if SENT_LABEL in labels:
        return SkipReason("sent")
    message = email.message_from_bytes(raw, policy=email.policy.default)
    if sender(message)[1].lower() == mailbox_email.lower():
        return SkipReason("from_mailbox")
    if _is_bounce(message):
        return SkipReason("bounce", original_message_id=_bounced_message_id(message))
    if _is_auto_reply(message):
        return SkipReason("auto_reply")
    return None
