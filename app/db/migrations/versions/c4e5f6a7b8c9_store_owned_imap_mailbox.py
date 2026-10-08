"""Clear legacy IMAP credentials and require one mailbox per store.

Revision ID: c4e5f6a7b8c9
Revises: b2c3d4e5f6a7
"""

from alembic import op
import sqlalchemy as sa

revision = "c4e5f6a7b8c9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM imap_mailboxes")
    with op.batch_alter_table("imap_mailboxes") as batch:
        batch.add_column(sa.Column("store_id", sa.String(), nullable=False))
        batch.create_unique_constraint("uq_imap_mailboxes_store_id", ["store_id"])


def downgrade() -> None:
    with op.batch_alter_table("imap_mailboxes") as batch:
        batch.drop_constraint("uq_imap_mailboxes_store_id", type_="unique")
        batch.drop_column("store_id")
