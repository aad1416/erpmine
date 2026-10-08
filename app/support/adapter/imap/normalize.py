"""Raw RFC 822 message fetched over IMAP -> NormalizedMessage.

Parsed with the standard library's modern email policy, which decodes RFC 2047 encoded
words in headers. Charsets Python doesn't know fall back to UTF-8 with replacement
instead of failing the message.

The caller picks the IDs. On Gmail they come from Gmail's IMAP extensions, hex-encoded
so they equal the Gmail API's message `id` and `threadId` for the same email
(`gmail_id_hex`). On other Mail Providers the message ID comes from the headers
(`header_message_key`) and a message that starts a Conversation names it
(`new_conversation_id`).
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from email.parser import BytesHeaderParser
from email.utils import parseaddr

from bs4 import BeautifulSoup

from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage


def gmail_id_hex(gm_id: int) -> str:
    """X-GM-MSGID / X-GM-THRID in the Gmail API's form: lowercase hex, no prefix."""
    return format(gm_id, "x")


def _decode_text_part(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()


def _extract_body_text(message: EmailMessage) -> str:
    plain = message.get_body(preferencelist=("plain",))
    if plain is not None:
        text = _decode_text_part(plain)
        if text.strip():
            return text.strip()

    html = message.get_body(preferencelist=("html",))
    if html is not None:
        return _html_to_text(_decode_text_part(html))

    return ""


def _has_attachments(message: EmailMessage) -> bool:
    return any(
        part.get_content_disposition() == "attachment" or part.get_filename()
        for part in message.walk()
        if not part.is_multipart()
    )


def sender(message: EmailMessage) -> tuple[str | None, str]:
    try:
        addresses = message["From"].addresses if message["From"] else ()
    except (AttributeError, IndexError, ValueError):
        addresses = ()
    if addresses:
        return addresses[0].display_name or None, addresses[0].addr_spec
    name, address = parseaddr(str(message.get("From", "")))
    return name or None, address


def normalize_imap_message(
    mailbox_key: MailboxKey,
    raw: bytes,
    external_message_id: str,
    conversation_id: str,
    received_at: datetime,
) -> NormalizedMessage:
    message = email.message_from_bytes(raw, policy=email.policy.default)
    sender_name, sender_address = sender(message)
    subject = message.get("Subject")

    return NormalizedMessage(
        adapter=mailbox_key.adapter,
        mailbox=mailbox_key.mailbox,
        conversation_id=conversation_id,
        external_message_id=external_message_id,
        sender_address=sender_address,
        sender_name=sender_name,
        received_at=received_at.astimezone(UTC),
        body_text=_extract_body_text(message),
        subject=str(subject) if subject is not None else None,
        has_attachments=_has_attachments(message),
    )


_MESSAGE_ID_TOKEN = re.compile(r"<[^<>]+>")


@dataclass(frozen=True)
class ThreadHeaders:
    """The headers a reply threads on. IDs keep their angle brackets."""

    message_id: str | None
    references: list[str]
    in_reply_to: list[str] = field(default_factory=list)


def message_ids(value) -> list[str]:
    if value is None:
        return []
    # Folded headers can leave whitespace inside a long ID.
    return [re.sub(r"\s+", "", token) for token in _MESSAGE_ID_TOKEN.findall(str(value))]


def read_thread_headers(raw: bytes) -> ThreadHeaders:
    """Message-ID and References of a raw message. A message with In-Reply-To but no
    References (some older clients) is treated as referencing its parent, per RFC 5322
    §3.6.4."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    ids = message_ids(message.get("Message-ID"))
    in_reply_to = message_ids(message.get("In-Reply-To"))
    references = message_ids(message.get("References")) or in_reply_to
    return ThreadHeaders(
        message_id=ids[0] if ids else None, references=references, in_reply_to=in_reply_to
    )


# Headers that identify a message without a Message-ID. Delivery headers (Received,
# Delivered-To) are left out, so the same message delivered twice keys the same.
_KEY_HEADERS = ("From", "To", "Cc", "Date", "Subject", "In-Reply-To", "References")


def header_message_key(raw: bytes, headers: ThreadHeaders) -> str:
    """The external message ID on a Mail Provider without Gmail's extensions: the
    Message-ID header, or, when it is missing, a hash of the key headers. Stable across
    re-fetches, so a message is captured once however often it is fetched."""
    if headers.message_id is not None:
        return headers.message_id
    # Raw header values, unfolded: no decoding step that could change between versions.
    raw_headers = BytesHeaderParser(policy=email.policy.default).parsebytes(raw).raw_items()
    values = [(name.lower(), " ".join(value.split())) for name, value in raw_headers]
    key = "\n".join(
        f"{name}:{value}"
        for name in (header.lower() for header in _KEY_HEADERS)
        for header_name, value in values
        if header_name == name
    )
    return "sha256:" + hashlib.sha256(key.encode("utf-8", errors="surrogateescape")).hexdigest()


def new_conversation_id(external_message_id: str) -> str:
    """The ID of a Conversation started by this message, on a Mail Provider without
    Gmail's extensions. Derived from the message's own ID, so a re-fetch lands in the
    same Conversation."""
    return hashlib.sha256(external_message_id.encode()).hexdigest()[:32]
