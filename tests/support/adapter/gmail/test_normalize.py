"""normalize.py is the component most likely to break on real-world message shapes
(08-unit-test-strategy-checklist.md §6) — dedicated fixtures for plain text, HTML-only,
multipart, and attachment-flagged messages."""

import base64

from app.support.adapter.gmail.normalize import normalize_gmail_message
from app.support.adapter.mailbox_key import MailboxKey

MAILBOX = MailboxKey("gmail", "s@x.com")


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _raw_message(payload: dict, subject="Compressor noise", sender="Jane Doe <jane@example.com>"):
    return {
        "id": "msg-1",
        "threadId": "thread-1",
        "internalDate": "1700000000000",
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ],
            **payload,
        },
    }


def test_plain_text_body():
    raw = _raw_message(
        {"mimeType": "text/plain", "body": {"data": _b64("The unit is making noise.")}}
    )
    msg = normalize_gmail_message(MAILBOX, raw)
    assert msg.body_text == "The unit is making noise."
    assert msg.subject == "Compressor noise"
    assert msg.sender_address == "jane@example.com"
    assert msg.sender_name == "Jane Doe"
    assert msg.conversation_id == "thread-1"
    assert msg.external_message_id == "msg-1"
    assert msg.has_attachments is False


def test_html_only_body_is_converted_to_plain_text():
    html = "<html><body><p>Hello</p><p>Unit broke <b>yesterday</b>.</p></body></html>"
    raw = _raw_message({"mimeType": "text/html", "body": {"data": _b64(html)}})
    msg = normalize_gmail_message(MAILBOX, raw)
    assert "Hello" in msg.body_text
    assert "Unit broke" in msg.body_text
    assert "yesterday" in msg.body_text
    assert "<b>" not in msg.body_text


def test_multipart_prefers_plain_text_over_html():
    raw = _raw_message(
        {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("Plain version")}},
                {"mimeType": "text/html", "body": {"data": _b64("<p>HTML version</p>")}},
            ],
        }
    )
    msg = normalize_gmail_message(MAILBOX, raw)
    assert msg.body_text == "Plain version"


def test_multipart_with_attachment_sets_has_attachments():
    raw = _raw_message(
        {
            "mimeType": "multipart/mixed",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("See attached invoice.")}},
                {
                    "mimeType": "application/pdf",
                    "filename": "invoice.pdf",
                    "body": {"attachmentId": "abc123"},
                },
            ],
        }
    )
    msg = normalize_gmail_message(MAILBOX, raw)
    assert msg.has_attachments is True
    assert msg.body_text == "See attached invoice."


def test_no_attachments_when_no_part_has_filename():
    raw = _raw_message(
        {"mimeType": "text/plain", "body": {"data": _b64("hi")}}
    )
    msg = normalize_gmail_message(MAILBOX, raw)
    assert msg.has_attachments is False


def test_nested_multipart_parts_are_walked():
    raw = _raw_message(
        {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64("Nested plain text")}},
                    ],
                },
            ],
        }
    )
    msg = normalize_gmail_message(MAILBOX, raw)
    assert msg.body_text == "Nested plain text"


def test_sender_without_display_name():
    raw = _raw_message(
        {"mimeType": "text/plain", "body": {"data": _b64("hi")}},
        sender="plain@example.com",
    )
    msg = normalize_gmail_message(MAILBOX, raw)
    assert msg.sender_address == "plain@example.com"
    assert msg.sender_name is None
