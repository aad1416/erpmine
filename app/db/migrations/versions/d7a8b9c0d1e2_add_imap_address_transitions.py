"""Keep IMAP address change windows and retired mailbox ownership.

Revision ID: d7a8b9c0d1e2
Revises: d6f8a93e12b4
"""

from alembic import op
import sqlalchemy as sa

revision = "d7a8b9c0d1e2"
down_revision = "d6f8a93e12b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "imap_address_transitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.String(), nullable=False),
        sa.Column("previous_mailbox", sa.String(), nullable=False),
        sa.Column("new_mailbox", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activation_error", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_imap_address_transitions_store_status",
        "imap_address_transitions",
        ["store_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_imap_address_transitions_store_status", table_name="imap_address_transitions")
    op.drop_table("imap_address_transitions")
