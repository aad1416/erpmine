"""add adapter and mailbox beside source_id

Expand step of the source ID split: every table that identifies a Mailbox by
`source_id = "<adapter>:<mailbox>"` gets `adapter` and `mailbox` columns beside it,
backfilled by splitting on the first `:`, with keys mirroring the source_id ones.
`source_id` stays until readers have moved over.

Not added to adapter_outbox_messages or adapter_cursors, which are dropped later in the
restructure; outbox payloads carry the fields anyway, via NormalizedMessage.

The columns stay nullable: a source_id without a `:` (the flat `mailtrap` one that
b7c1d2e3f4a5 leaves alone when no inbox address is set) has no mailbox to split out, so
its row keeps NULLs.

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "ingestion_tasks",
    "conversations",
    "imap_thread_messages",
    "gmail_watches",
)


def _split(source_id: str) -> tuple[str, str] | None:
    """Frozen copy of MailboxKey.from_source_id: the app helper moves on while this
    migration must not."""
    adapter, separator, address = source_id.partition(":")
    if not separator or not adapter or not address:
        return None
    return adapter, address.lower()


def _backfill(table: str) -> None:
    """Split in Python, one UPDATE per distinct source_id: portable across SQLite and
    Postgres, and source_ids are few (one per Mailbox)."""
    connection = op.get_bind()
    source_ids = connection.execute(
        sa.text(f"SELECT DISTINCT source_id FROM {table}")
    ).scalars().all()
    for source_id in source_ids:
        split = _split(source_id)
        if split is None:
            continue
        adapter, mailbox = split
        connection.execute(
            sa.text(
                f"UPDATE {table} SET adapter = :adapter, mailbox = :mailbox "
                "WHERE source_id = :source_id"
            ),
            {"adapter": adapter, "mailbox": mailbox, "source_id": source_id},
        )


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('adapter', sa.String(), nullable=True))
            batch_op.add_column(sa.Column('mailbox', sa.String(), nullable=True))
        _backfill(table)

    with op.batch_alter_table("ingestion_tasks") as batch_op:
        batch_op.create_unique_constraint(
            "uq_ingestion_task_adapter_mailbox_dedup",
            ["task_type", "adapter", "mailbox", "external_message_id"],
        )
        batch_op.create_index(
            "ix_ingestion_tasks_adapter_mailbox_conversation",
            ["adapter", "mailbox", "conversation_id"],
        )
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.create_unique_constraint(
            "uq_conversation_adapter_mailbox_conversation_id",
            ["adapter", "mailbox", "conversation_id"],
        )
        batch_op.create_index("ix_conversations_mailbox", ["mailbox"])
    with op.batch_alter_table("imap_thread_messages") as batch_op:
        batch_op.create_unique_constraint(
            "uq_imap_thread_adapter_mailbox_message_id",
            ["adapter", "mailbox", "message_id"],
        )
        batch_op.create_index(
            "ix_imap_thread_adapter_mailbox_conversation",
            ["adapter", "mailbox", "conversation_id"],
        )
    with op.batch_alter_table("gmail_watches") as batch_op:
        batch_op.create_unique_constraint(
            "uq_gmail_watch_adapter_mailbox", ["adapter", "mailbox"]
        )


def downgrade() -> None:
    with op.batch_alter_table("gmail_watches") as batch_op:
        batch_op.drop_constraint("uq_gmail_watch_adapter_mailbox", type_="unique")
    with op.batch_alter_table("imap_thread_messages") as batch_op:
        batch_op.drop_index("ix_imap_thread_adapter_mailbox_conversation")
        batch_op.drop_constraint("uq_imap_thread_adapter_mailbox_message_id", type_="unique")
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_index("ix_conversations_mailbox")
        batch_op.drop_constraint(
            "uq_conversation_adapter_mailbox_conversation_id", type_="unique"
        )
    with op.batch_alter_table("ingestion_tasks") as batch_op:
        batch_op.drop_index("ix_ingestion_tasks_adapter_mailbox_conversation")
        batch_op.drop_constraint("uq_ingestion_task_adapter_mailbox_dedup", type_="unique")

    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('mailbox')
            batch_op.drop_column('adapter')
