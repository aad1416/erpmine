"""add unique constraints for support idempotency

Revision ID: a1b2c3d4e5f7
Revises: 0ebd5e9cf387
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = '0ebd5e9cf387'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversation_messages") as batch_op:
        batch_op.create_unique_constraint(
            "uq_conversation_message_dedup",
            ["conversation_id", "external_message_id"],
        )
    with op.batch_alter_table("pending_log_syncs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_pending_log_sync_message",
            ["conversation_message_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("pending_log_syncs") as batch_op:
        batch_op.drop_constraint("uq_pending_log_sync_message", type_="unique")
    with op.batch_alter_table("conversation_messages") as batch_op:
        batch_op.drop_constraint("uq_conversation_message_dedup", type_="unique")
