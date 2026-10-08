"""Raw RFC 822 bytes -> NormalizedMessage: the real-world MIME shapes most likely to
break parsing."""

from datetime import UTC, datetime, timedelta, timezone

from app.support.adapter.imap.normalize import (
    gmail_id_hex,
    header_message_key,
    new_conversation_id,
    normalize_imap_message,
    read_thread_headers,
)
from app.support.adapter.mailbox_key import MailboxKey

MAILBOX = MailboxKey("imap", "support@acme-store.com")


def _normalize(raw: str | bytes, received_at=datetime(2026, 9, 25, 9, 0, tzinfo=UTC)):
    if isinstance(raw, str):
        raw = raw.replace("\n", "\r\n").encode()
    return normalize_imap_message(
        MAILBOX,
        raw,
        external_message_id=gmail_id_hex(255),
        conversation_id=gmail_id_hex(4096),
        received_at=received_at,
    )


def test_plain_text_message():
    msg = _normalize(
        "From: Jane Doe <jane@example.com>\n"
        "Subject: Compressor noise\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "The unit is making noise.\n"
    )
    assert (msg.adapter, msg.mailbox) == ("imap", "support@acme-store.com")
    assert msg.external_message_id == "ff"
    assert msg.conversation_id == "1000"
    assert msg.sender_name == "Jane Doe"
    assert msg.sender_address == "jane@example.com"
    assert msg.subject == "Compressor noise"
    assert msg.body_text == "The unit is making noise."
    assert msg.has_attachments is False


def test_multipart_alternative_prefers_plain_text():
    msg = _normalize(
        "From: jane@example.com\n"
        "Subject: Hi\n"
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/alternative; boundary="b1"\n'
        "\n"
        "--b1\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Plain version\n"
        "--b1\n"
        "Content-Type: text/html; charset=utf-8\n"
        "\n"
        "<p>HTML version</p>\n"
        "--b1--\n"
    )
    assert msg.body_text == "Plain version"
    assert msg.sender_name is None
    assert msg.sender_address == "jane@example.com"


def test_html_only_body_is_stripped_to_text():
    msg = _normalize(
        "From: jane@example.com\n"
        "Subject: Hi\n"
        "Content-Type: text/html; charset=utf-8\n"
        "\n"
        "<html><body><p>Hello</p><p>Unit broke <b>yesterday</b>.</p></body></html>\n"
    )
    assert "Hello" in msg.body_text
    assert "yesterday" in msg.body_text
    assert "<" not in msg.body_text


def test_rfc2047_encoded_headers_are_decoded():
    msg = _normalize(
        "From: =?UTF-8?B?Sm9zw6kgR2FyY8OtYQ==?= <jose@example.com>\n"
        "Subject: =?ISO-8859-1?Q?R=E9paration_urgente?=\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Body\n"
    )
    assert msg.sender_name == "José García"
    assert msg.subject == "Réparation urgente"


def test_unknown_charset_falls_back_instead_of_failing():
    msg = _normalize(
        b"From: jane@example.com\r\n"
        b"Subject: Hi\r\n"
        b"Content-Type: text/plain; charset=x-no-such-charset\r\n"
        b"Content-Transfer-Encoding: 8bit\r\n"
        b"\r\n"
        b"Caf\xc3\xa9 unit \xff broken\r\n"
    )
    assert "Café unit" in msg.body_text
    assert "broken" in msg.body_text


def test_attachment_sets_flag_only():
    msg = _normalize(
        "From: jane@example.com\n"
        "Subject: Photo\n"
        "MIME-Version: 1.0\n"
        'Content-Type: multipart/mixed; boundary="b1"\n'
        "\n"
        "--b1\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "See attached.\n"
        "--b1\n"
        "Content-Type: image/png\n"
        'Content-Disposition: attachment; filename="unit.png"\n'
        "Content-Transfer-Encoding: base64\n"
        "\n"
        "iVBORw0KGgo=\n"
        "--b1--\n"
    )
    assert msg.has_attachments is True
    assert msg.body_text == "See attached."


def test_received_at_is_converted_to_utc():
    tehran = timezone(timedelta(hours=3, minutes=30))
    msg = _normalize(
        "From: jane@example.com\n\nBody\n",
        received_at=datetime(2026, 9, 25, 12, 30, tzinfo=tehran),
    )
    assert msg.received_at == datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    assert msg.subject is None


def test_gmail_ids_are_lowercase_hex_without_prefix():
    assert gmail_id_hex(1278455344230334865) == "11bdfc5cae0c8191"


def _headers(raw: str):
    return read_thread_headers(raw.replace("\n", "\r\n").encode())


def test_thread_headers_read_message_id_and_folded_references():
    headers = _headers(
        "From: jane@example.com\n"
        "Message-ID: <m3@example.com>\n"
        "In-Reply-To: <m2@example.com>\n"
        "References: <m1@example.com>\n"
        " <m2@example.com>\n"
        "\n"
        "Body\n"
    )
    assert headers.message_id == "<m3@example.com>"
    assert headers.references == ["<m1@example.com>", "<m2@example.com>"]


def test_thread_headers_fall_back_to_in_reply_to_without_references():
    headers = _headers(
        "From: jane@example.com\nMessage-ID: <m2@example.com>\nIn-Reply-To: <m1@example.com>\n\nBody\n"
    )
    assert headers.references == ["<m1@example.com>"]


def test_thread_headers_without_message_id():
    headers = _headers("From: jane@example.com\n\nBody\n")
    assert headers.message_id is None
    assert headers.references == []


def _key(raw: str) -> str:
    raw_bytes = raw.replace("\n", "\r\n").encode()
    return header_message_key(raw_bytes, read_thread_headers(raw_bytes))


_NO_MESSAGE_ID = (
    "From: Jane <jane@example.com>\n"
    "To: support@acme-store.com\n"
    "Date: Fri, 25 Sep 2026 09:00:00 +0000\n"
    "Subject: Help\n"
    "\n"
    "Body\n"
)


def test_header_message_key_is_the_message_id_when_present():
    assert _key("Message-ID: <a@example.com>\n" + _NO_MESSAGE_ID) == "<a@example.com>"


def test_header_message_key_without_message_id_is_a_stable_hash_of_key_headers():
    key = _key(_NO_MESSAGE_ID)
    assert key.startswith("sha256:")
    assert _key(_NO_MESSAGE_ID) == key
    # Delivery headers and the body don't change it; a key header does.
    assert _key("Received: from mx2.example.com\n" + _NO_MESSAGE_ID.replace("Body", "Other")) == key
    assert _key(_NO_MESSAGE_ID.replace("Subject: Help", "Subject: Help 2")) != key


def test_new_conversation_id_is_derived_from_the_message_id():
    assert new_conversation_id("<a@example.com>") == new_conversation_id("<a@example.com>")
    assert new_conversation_id("<a@example.com>") != new_conversation_id("<b@example.com>")
    assert len(new_conversation_id("<a@example.com>")) == 32


def test_thread_headers_keep_in_reply_to_apart_from_references():
    headers = read_thread_headers(
        b"Message-ID: <c@x>\r\nIn-Reply-To: <b@x>\r\nReferences: <a@x> <b@x>\r\n\r\n"
    )
    assert headers.in_reply_to == ["<b@x>"]
    assert headers.references == ["<a@x>", "<b@x>"]
