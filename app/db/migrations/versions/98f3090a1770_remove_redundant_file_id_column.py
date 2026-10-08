"""remove_redundant_file_id_column

Revision ID: 98f3090a1770
Revises: 05fa45f9036b
Create Date: 2025-12-28 01:43:31.686417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98f3090a1770'
down_revision: Union[str, Sequence[str], None] = '05fa45f9036b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the index first, then drop the column
    op.drop_index(op.f('ix_files_file_id'), table_name='files')
    op.drop_column('files', 'file_id')


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add the column and index if we need to rollback
    op.add_column('files', sa.Column('file_id', sa.String(), nullable=False))
    op.create_index(op.f('ix_files_file_id'), 'files', ['file_id'], unique=True)
