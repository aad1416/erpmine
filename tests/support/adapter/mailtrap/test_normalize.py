"""normalize.py mapping — no MIME variation to cover here (unlike Gmail's multipart
matrix), so this is the adapter's easiest, most deterministic test surface
(11-mailtrap-adapter-plan.md §1, §8)."""

from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.mailtrap.normalize import normalize_mailtrap_message

MAILBOX = MailboxKey("mailtrap", "dev@inbox.mailtrap.io")


def _raw_message(
    text_body="The unit is making noise.",
    html_body=None,
    thread_id="thread-1",
    sender="Jane Doe <jane@example.com>",
    attachments=None,
):
    return {
        "id": "msg-1",
        "thread_id": thread_id,
        "from": sender,
        "subject": "Compressor noise",
        "received_at": "2024-01-15T10:30:00.000Z",
        "text_body": text_body,
        "html_body": html_body,
        "attachments": attachments or [],
    }


def test_plain_text_body():
    raw = _raw_message()
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert msg.body_text == "The unit is making noise."
    assert msg.subject == "Compressor noise"
    assert msg.sender_address == "jane@example.com"
    assert msg.sender_name == "Jane Doe"
    assert msg.conversation_id == "thread-1"
    assert msg.external_message_id == "msg-1"
    assert msg.has_attachments is False


def test_null_text_body_falls_back_to_html():
    html = "<html><body><p>Hello</p><p>Unit broke <b>yesterday</b>.</p></body></html>"
    raw = _raw_message(text_body=None, html_body=html)
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert "Hello" in msg.body_text
    assert "Unit broke" in msg.body_text
    assert "yesterday" in msg.body_text
    assert "<b>" not in msg.body_text


def test_null_thread_id_falls_back_to_message_id():
    raw = _raw_message(thread_id=None)
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert msg.conversation_id == "msg-1"


def test_sender_without_display_name():
    raw = _raw_message(sender="plain@example.com")
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert msg.sender_address == "plain@example.com"
    assert msg.sender_name is None


def test_attachments_present_sets_has_attachments():
    raw = _raw_message(
        attachments=[{"attachment_id": "a1", "filename": "invoice.pdf", "size": 123}]
    )
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert msg.has_attachments is True


def test_no_attachments_when_list_is_empty():
    raw = _raw_message(attachments=[])
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert msg.has_attachments is False


def test_mailbox_is_carried_through():
    raw = _raw_message()
    msg = normalize_mailtrap_message(MAILBOX, raw)
    assert (msg.adapter, msg.mailbox) == ("mailtrap", "dev@inbox.mailtrap.io")
