"""drop source_id and the shared adapter tables

Contract step of the source ID split and the Mailbox Adapter restructure. Every Mailbox
Adapter now keeps its own cursor and outbox, and every reader uses `adapter` + `mailbox`,
so:

1. Rows whose `adapter` / `mailbox` d5e6f7a8b9c0 left NULL are resolved first, since both
   columns become NOT NULL. The only such source ID is the flat `mailtrap` one, from
   before Mailtrap was namespaced per inbox. It is backfilled with the inbox address from
   `MAILTRAP_INBOX_ADDRESS_1` (or its older name `MAILTRAP_INBOX_ADDRESS`) when that is
   set in the environment, as b7c1d2e3f4a5 would have done. Every row still NULL after
   that has no Mailbox to route to and is deleted, with a Conversation's messages and
   pending log syncs. The number deleted per table is logged.
2. Stored message payloads written before messages carried `adapter` + `mailbox` (message
   tasks, and the Gmail and IMAP outboxes, which copied them from the shared outbox) get
   both from their row, so nothing needs to split a source ID to read them.
3. The shared `adapter_outbox_messages` and `adapter_cursors` tables are dropped. The
   adapter migrations (e7f8a9b0c1d2, f8a9b0c1d2e3, a0b1c2d3e4f5) already copied what
   their adapters need out of them.
4. `source_id` is dropped from ingestion_tasks, conversations, imap_thread_messages and
   gmail_watches with its unique keys and indexes, and `adapter` / `mailbox` become NOT
   NULL. gmail_watches, keyed by source_id, is keyed by (adapter, mailbox) instead.

Downgrade restores the columns (rebuilt as `<adapter>:<mailbox>`), keys and nullability,
and recreates the two shared tables empty. Deleted rows and their contents do not come
back; the payload fields added in step 2 stay, and are harmless to the older code.

Revision ID: b2c3d4e5f6a7
Revises: a0b1c2d3e4f5
Create Date: 2026-09-26

"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pydantic_settings import BaseSettings, SettingsConfigDict


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(f"alembic.{revision}")

_TABLES = (
    "ingestion_tasks",
    "conversations",
    "imap_thread_messages",
    "gmail_watches",
)

_FLAT_MAILTRAP_SOURCE_ID = "mailtrap"


class _LegacyMailtrapInbox(BaseSettings):
    """Frozen here, not read from the app settings, which no longer have it."""

    model_config = SettingsConfigDict(
        extra="ignore", env_file=".env", env_file_encoding="utf-8"
    )

    MAILTRAP_INBOX_ADDRESS_1: str | None = None
    MAILTRAP_INBOX_ADDRESS: str | None = None

    def address(self) -> str | None:
        address = self.MAILTRAP_INBOX_ADDRESS_1 or self.MAILTRAP_INBOX_ADDRESS
        return address.lower() if address else None


def _backfill_flat_mailtrap() -> None:
    """Skips a row whose backfilled key another row already has, which is then deleted
    as unroutable rather than breaking a unique key."""
    address = _LegacyMailtrapInbox().address()
    if address is None:
        return
    connection = op.get_bind()
    parameters = {"address": address, "flat": _FLAT_MAILTRAP_SOURCE_ID}
    connection.execute(
        sa.text(
            "UPDATE conversations SET adapter = 'mailtrap', mailbox = :address "
            "WHERE source_id = :flat AND (adapter IS NULL OR mailbox IS NULL) "
            "AND NOT EXISTS (SELECT 1 FROM conversations AS existing "
            "WHERE existing.adapter = 'mailtrap' AND existing.mailbox = :address "
            "AND existing.conversation_id = conversations.conversation_id)"
        ),
        parameters,
    )
    connection.execute(
        sa.text(
            "UPDATE ingestion_tasks SET adapter = 'mailtrap', mailbox = :address "
            "WHERE source_id = :flat AND (adapter IS NULL OR mailbox IS NULL) "
            "AND NOT EXISTS (SELECT 1 FROM ingestion_tasks AS existing "
            "WHERE existing.adapter = 'mailtrap' AND existing.mailbox = :address "
            "AND existing.task_type = ingestion_tasks.task_type "
            "AND existing.external_message_id = ingestion_tasks.external_message_id)"
        ),
        parameters,
    )


def _delete_unroutable() -> None:
    connection = op.get_bind()
    unroutable = "adapter IS NULL OR mailbox IS NULL"
    unroutable_conversations = (
        f"SELECT id FROM conversations WHERE {unroutable}"
    )
    unroutable_messages = (
        "SELECT id FROM conversation_messages "
        f"WHERE conversation_id IN ({unroutable_conversations})"
    )
    deletions = (
        ("pending_log_syncs", f"conversation_message_id IN ({unroutable_messages})"),
        ("conversation_messages", f"conversation_id IN ({unroutable_conversations})"),
        *((table, unroutable) for table in _TABLES),
    )
    for table, condition in deletions:
        deleted = connection.execute(sa.text(f"DELETE FROM {table} WHERE {condition}")).rowcount
        if deleted:
            logger.warning(
                "Deleted %d %s row(s) with no adapter + mailbox to route to", deleted, table
            )


def _fill_payload_identities(
    table: str, payload_column: str, fixed_adapter: str | None = None, where: str = ""
) -> None:
    """Adds `adapter` and `mailbox` to each payload missing them, from its row."""
    connection = op.get_bind()
    columns = [sa.column("id"), sa.column("mailbox"), sa.column(payload_column, sa.JSON)]
    if fixed_adapter is None:
        columns.append(sa.column("adapter"))
    table_clause = sa.table(table, *columns)
    query = sa.select(*table_clause.columns)
    if where:
        query = query.where(sa.text(where))
    update = (
        sa.update(table_clause)
        .where(table_clause.c.id == sa.bindparam("row_id"))
        .values({payload_column: sa.bindparam("payload", type_=sa.JSON)})
    )
    for row in connection.execute(query).mappings().all():
        payload = row[payload_column]
        if not isinstance(payload, dict) or (payload.get("adapter") and payload.get("mailbox")):
            continue
        adapter = fixed_adapter or row["adapter"]
        connection.execute(
            update,
            {"row_id": row["id"], "payload": {**payload, "adapter": adapter, "mailbox": row["mailbox"]}},
        )


def upgrade() -> None:
    _backfill_flat_mailtrap()
    _delete_unroutable()

    _fill_payload_identities("ingestion_tasks", "payload", where="task_type = 'message'")
    _fill_payload_identities("gmail_outbox", "normalized_payload", fixed_adapter="gmail")
    _fill_payload_identities("imap_outbox", "normalized_payload", fixed_adapter="imap")

    op.drop_index('ix_adapter_outbox_messages_source_id', table_name='adapter_outbox_messages')
    op.drop_index(
        'ix_adapter_outbox_messages_conversation_id', table_name='adapter_outbox_messages'
    )
    op.drop_table('adapter_outbox_messages')
    op.drop_table('adapter_cursors')

    with op.batch_alter_table("ingestion_tasks") as batch_op:
        batch_op.drop_constraint("uq_ingestion_task_dedup", type_="unique")
        batch_op.drop_column("source_id")
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=False)
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint("uq_conversation_source_conversation_id", type_="unique")
        batch_op.drop_index("ix_conversations_source_id")
        batch_op.drop_column("source_id")
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=False)
    with op.batch_alter_table("imap_thread_messages") as batch_op:
        batch_op.drop_constraint("uq_imap_thread_source_message_id", type_="unique")
        batch_op.drop_index("ix_imap_thread_source_conversation")
        batch_op.drop_column("source_id")
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=False)
    with op.batch_alter_table("gmail_watches") as batch_op:
        batch_op.drop_constraint("uq_gmail_watch_adapter_mailbox", type_="unique")
        # Dropping the primary key column drops its key.
        batch_op.drop_column("source_id")
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=False)
        batch_op.create_primary_key("pk_gmail_watches", ["adapter", "mailbox"])


def downgrade() -> None:
    connection = op.get_bind()
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("source_id", sa.String(), nullable=True))
        connection.execute(sa.text(f"UPDATE {table} SET source_id = adapter || ':' || mailbox"))

    with op.batch_alter_table("gmail_watches") as batch_op:
        batch_op.drop_constraint("pk_gmail_watches", type_="primary")
        batch_op.alter_column("source_id", existing_type=sa.String(), nullable=False)
        batch_op.create_primary_key("pk_gmail_watches", ["source_id"])
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=True)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=True)
        batch_op.create_unique_constraint("uq_gmail_watch_adapter_mailbox", ["adapter", "mailbox"])
    with op.batch_alter_table("imap_thread_messages") as batch_op:
        batch_op.alter_column("source_id", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=True)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=True)
        batch_op.create_unique_constraint(
            "uq_imap_thread_source_message_id", ["source_id", "message_id"]
        )
        batch_op.create_index(
            "ix_imap_thread_source_conversation", ["source_id", "conversation_id"]
        )
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.alter_column("source_id", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=True)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=True)
        batch_op.create_index("ix_conversations_source_id", ["source_id"])
        batch_op.create_unique_constraint(
            "uq_conversation_source_conversation_id", ["source_id", "conversation_id"]
        )
    with op.batch_alter_table("ingestion_tasks") as batch_op:
        batch_op.alter_column("source_id", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("adapter", existing_type=sa.String(), nullable=True)
        batch_op.alter_column("mailbox", existing_type=sa.String(), nullable=True)
        batch_op.create_unique_constraint(
            "uq_ingestion_task_dedup", ["task_type", "source_id", "external_message_id"]
        )

    op.create_table('adapter_cursors',
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('cursor_value', sa.String(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('source_id')
    )
    op.create_table('adapter_outbox_messages',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('external_message_id', sa.String(), nullable=False),
    sa.Column('conversation_id', sa.String(), nullable=False),
    sa.Column('normalized_payload', sa.JSON(), nullable=False),
    sa.Column('captured_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('published_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'external_message_id', name='uq_outbox_source_external_message')
    )
    op.create_index(op.f('ix_adapter_outbox_messages_conversation_id'), 'adapter_outbox_messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_adapter_outbox_messages_source_id'), 'adapter_outbox_messages', ['source_id'], unique=False)
