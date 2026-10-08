"""add mailtrap mailbox tables

The Mailtrap adapter's own tables: `mailtrap_mailboxes` (its Mailbox Connection table,
keyed by inbox address, holding the encrypted API token, inbox ID and cursor),
`mailtrap_last_inbound_messages` (what a reply targets) and `mailtrap_sent_replies`
(reply idempotency).

Carries existing state over so deploying neither cold-starts nor loses reply targets:
- each `mailtrap:<address>` cursor in `adapter_cursors` becomes a `mailtrap_mailboxes`
  row with that cursor and no credentials yet, which the seeder fills in. The flat
  `mailtrap` source ID has no address and is skipped.
- the newest captured message of each Mailtrap Conversation still in
  `adapter_outbox_messages` becomes its last inbound message.

The old rows are copied, not moved: `adapter_cursors` and the outbox are dropped later.

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-09-26

"""
import json
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mailtrap_address(source_id: str) -> str | None:
    """Frozen split of a `mailtrap:<address>` source ID, lower-cased as addresses are
    stored."""
    adapter, separator, address = source_id.partition(":")
    if adapter != "mailtrap" or not separator or not address:
        return None
    return address.lower()


def upgrade() -> None:
    mailboxes = op.create_table(
        "mailtrap_mailboxes",
        sa.Column("mailbox", sa.String(), primary_key=True),
        sa.Column("inbox_id", sa.String(), nullable=True),
        sa.Column("api_token", sa.Text(), nullable=True),
        sa.Column("cursor", sa.String(), nullable=True),
    )
    last_inbound_messages = op.create_table(
        "mailtrap_last_inbound_messages",
        sa.Column("mailbox", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), primary_key=True),
        sa.Column("external_message_id", sa.String(), nullable=False),
        sa.Column("received_at", sa.String(), nullable=False),
    )
    op.create_table(
        "mailtrap_sent_replies",
        sa.Column("idempotency_key", sa.String(), primary_key=True),
        sa.Column("mailbox", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
    )

    connection = op.get_bind()

    cursors_by_mailbox: dict[str, str | None] = {}
    for source_id, cursor_value in connection.execute(
        sa.text(
            "SELECT source_id, cursor_value FROM adapter_cursors "
            "WHERE source_id LIKE 'mailtrap:%'"
        )
    ):
        mailbox = _mailtrap_address(source_id)
        if mailbox is not None and mailbox not in cursors_by_mailbox:
            cursors_by_mailbox[mailbox] = cursor_value
    if cursors_by_mailbox:
        op.bulk_insert(
            mailboxes,
            [
                {"mailbox": mailbox, "cursor": cursor_value}
                for mailbox, cursor_value in cursors_by_mailbox.items()
            ],
        )

    newest_by_conversation: dict[tuple[str, str], tuple[datetime, str, str]] = {}
    for source_id, conversation_id, external_message_id, payload in connection.execute(
        sa.text(
            "SELECT source_id, conversation_id, external_message_id, normalized_payload "
            "FROM adapter_outbox_messages WHERE source_id LIKE 'mailtrap:%'"
        )
    ):
        mailbox = _mailtrap_address(source_id)
        if isinstance(payload, str):
            payload = json.loads(payload)
        received_at = (payload or {}).get("received_at")
        if mailbox is None or not received_at:
            continue
        key = (mailbox, conversation_id)
        received_at_value = datetime.fromisoformat(received_at)
        newest = newest_by_conversation.get(key)
        if newest is None or newest[0] <= received_at_value:
            newest_by_conversation[key] = (received_at_value, received_at, external_message_id)
    if newest_by_conversation:
        op.bulk_insert(
            last_inbound_messages,
            [
                {
                    "mailbox": mailbox,
                    "conversation_id": conversation_id,
                    "external_message_id": external_message_id,
                    "received_at": received_at,
                }
                for (mailbox, conversation_id), (
                    _received_at_value,
                    received_at,
                    external_message_id,
                ) in newest_by_conversation.items()
            ],
        )


def downgrade() -> None:
    op.drop_table("mailtrap_sent_replies")
    op.drop_table("mailtrap_last_inbound_messages")
    op.drop_table("mailtrap_mailboxes")
