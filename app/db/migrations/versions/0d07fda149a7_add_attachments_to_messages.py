"""add attachments to messages

Nullable JSON column holding the Outputs (chart/table/file) a reports-agent
assistant message produced (map decision D5). NULL for every existing row and
every non-Report message; only the reports agent runner writes it.

Revision ID: 0d07fda149a7
Revises: b7c1d2e3f4a5
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d07fda149a7'
down_revision: Union[str, Sequence[str], None] = 'b7c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('messages', sa.Column('attachments', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('messages', 'attachments')
