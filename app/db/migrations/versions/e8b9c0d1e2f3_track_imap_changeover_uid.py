"""Remember the first successful new-inbox UID checkpoint during IMAP changeover.

Revision ID: e8b9c0d1e2f3
Revises: d7a8b9c0d1e2
"""

from alembic import op
import sqlalchemy as sa

revision = "e8b9c0d1e2f3"
down_revision = "d7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("imap_address_transitions") as batch_op:
        batch_op.add_column(sa.Column("new_uidvalidity", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("new_uidnext", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("new_endpoint", sa.String(), nullable=True))
        batch_op.add_column(sa.Column(
            "backfill_review_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ))


def downgrade() -> None:
    with op.batch_alter_table("imap_address_transitions") as batch_op:
        batch_op.drop_column("backfill_review_required")
        batch_op.drop_column("new_endpoint")
        batch_op.drop_column("new_uidnext")
        batch_op.drop_column("new_uidvalidity")
