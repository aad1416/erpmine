"""add gmail mailbox tables

The Gmail API adapter's own tables: `gmail_mailboxes` (its Mailbox Connection table,
keyed by address, holding the encrypted refresh token and the history cursor),
`gmail_outbox` (messages captured but not yet handed to ingestion) and
`gmail_sent_replies` (reply idempotency). `gmail_watches` already exists and is kept.

Carries existing state over so deploying neither cold-starts nor loses mail:
- each `gmail:<address>` cursor in `adapter_cursors` becomes a `gmail_mailboxes` row with
  that history cursor and no refresh token yet, which the seeder fills in.
- each Gmail message still `captured` in `adapter_outbox_messages` (its cursor has moved
  past it, but ingestion never took it) becomes an undelivered `gmail_outbox` row, which
  the adapter re-sinks when it starts.

The old rows are copied, not moved: `adapter_cursors` and the outbox are dropped later.

Revision ID: a0b1c2d3e4f5
Revises: f8a9b0c1d2e3
Create Date: 2026-09-26

"""
import json
from datetime import datetime, UTC
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _gmail_address(source_id: str) -> str | None:
    """Frozen split of a `gmail:<address>` source ID, lower-cased as addresses are
    stored."""
    adapter, separator, address = source_id.partition(":")
    if adapter != "gmail" or not separator or not address:
        return None
    return address.lower()


def upgrade() -> None:
    mailboxes = op.create_table(
        "gmail_mailboxes",
        sa.Column("mailbox", sa.String(), primary_key=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("history_id", sa.String(), nullable=True),
    )
    outbox = op.create_table(
        "gmail_outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mailbox", sa.String(), nullable=False),
        sa.Column("external_message_id", sa.String(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "mailbox", "external_message_id", name="uq_gmail_outbox_mailbox_message"
        ),
    )
    op.create_index("ix_gmail_outbox_mailbox_status", "gmail_outbox", ["mailbox", "status"])
    op.create_table(
        "gmail_sent_replies",
        sa.Column("idempotency_key", sa.String(), primary_key=True),
        sa.Column("mailbox", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )

    connection = op.get_bind()

    cursors_by_mailbox: dict[str, str | None] = {}
    for source_id, cursor_value in connection.execute(
        sa.text(
            "SELECT source_id, cursor_value FROM adapter_cursors "
            "WHERE source_id LIKE 'gmail:%'"
        )
    ):
        mailbox = _gmail_address(source_id)
        if mailbox is not None and mailbox not in cursors_by_mailbox:
            cursors_by_mailbox[mailbox] = cursor_value
    if cursors_by_mailbox:
        op.bulk_insert(
            mailboxes,
            [
                {"mailbox": mailbox, "history_id": cursor_value}
                for mailbox, cursor_value in cursors_by_mailbox.items()
            ],
        )

    captured_at = datetime.now(UTC)
    undelivered: dict[tuple[str, str], dict] = {}
    # Oldest first, so the outbox's capture order (its id) matches the old one.
    for source_id, external_message_id, payload in connection.execute(
        sa.text(
            "SELECT source_id, external_message_id, normalized_payload "
            "FROM adapter_outbox_messages "
            "WHERE source_id LIKE 'gmail:%' AND status = 'captured' "
            "ORDER BY captured_at"
        )
    ):
        mailbox = _gmail_address(source_id)
        if mailbox is None:
            continue
        if isinstance(payload, str):
            payload = json.loads(payload)
        undelivered.setdefault(
            (mailbox, external_message_id),
            {
                "mailbox": mailbox,
                "external_message_id": external_message_id,
                "normalized_payload": payload,
                "status": "captured",
                "captured_at": captured_at,
            },
        )
    if undelivered:
        op.bulk_insert(outbox, list(undelivered.values()))


def downgrade() -> None:
    op.drop_table("gmail_sent_replies")
    op.drop_index("ix_gmail_outbox_mailbox_status", table_name="gmail_outbox")
    op.drop_table("gmail_outbox")
    op.drop_table("gmail_mailboxes")
