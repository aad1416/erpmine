"""Record acknowledgement of IMAP transition warnings.

Revision ID: f9c0d1e2a3b4
Revises: e8b9c0d1e2f3
"""

from alembic import op
import sqlalchemy as sa

revision = "f9c0d1e2a3b4"
down_revision = "e8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("imap_address_transitions") as batch_op:
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("imap_address_transitions") as batch_op:
        batch_op.drop_column("reviewed_at")
