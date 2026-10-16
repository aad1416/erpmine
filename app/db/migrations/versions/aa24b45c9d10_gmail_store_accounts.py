"""Add store ownership and an enabled flag to Gmail mailbox connections.

Existing seeded accounts remain active and unassigned until their store is identified.

Revision ID: aa24b45c9d10
Revises: f9c0d1e2a3b4
"""

from alembic import op
import sqlalchemy as sa

revision = "aa24b45c9d10"
down_revision = "f9c0d1e2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("gmail_mailboxes") as batch:
        batch.add_column(sa.Column("store_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"))
        batch.create_index("ix_gmail_mailboxes_store_id", ["store_id"])


def downgrade() -> None:
    with op.batch_alter_table("gmail_mailboxes") as batch:
        batch.drop_index("ix_gmail_mailboxes_store_id")
        batch.drop_column("enabled")
        batch.drop_column("store_id")
