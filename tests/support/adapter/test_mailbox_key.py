"""MailboxKey: a Mailbox's identity, its adapter name and lower-cased address."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.schemas import NormalizedMessage


def test_the_address_is_stored_lower_cased():
    assert MailboxKey.of("imap", "Help@Shop.com") == MailboxKey("imap", "help@shop.com")


def test_the_deprecated_source_id_is_adapter_and_lowercased_address():
    """Only support monitoring reads it, for the panel that still builds URLs from it."""
    assert MailboxKey.of("imap", "Help@Shop.com").source_id == "imap:help@shop.com"


@pytest.mark.parametrize("adapter, mailbox", [(None, None), ("imap", None), ("", "a@b.com")])
def test_a_mailbox_needs_both_parts(adapter, mailbox):
    """A reply can't be routed to an empty adapter or address."""
    with pytest.raises(ValueError):
        MailboxKey(adapter, mailbox)


def _message(**identity) -> NormalizedMessage:
    return NormalizedMessage(
        **identity,
        conversation_id="t1",
        external_message_id="m1",
        sender_address="a@b.com",
        received_at=datetime.now(UTC),
        body_text="hi",
    )


def test_a_normalized_message_carries_its_mailbox_lower_cased():
    message = _message(adapter="imap", mailbox="Help@Shop.com")
    assert message.mailbox_key == MailboxKey("imap", "help@shop.com")


def test_a_payload_with_only_a_source_id_is_rejected():
    """Stored payloads were given adapter + mailbox by migration b2c3d4e5f6a7, so
    nothing splits a source ID any more."""
    with pytest.raises(ValidationError):
        _message(source_id="imap:help@shop.com")
