"""make_store_id_and_name_be_uniqute

Revision ID: 2a741e71dfc9
Revises: 8c4b376c6ba4
Create Date: 2026-03-11 06:45:12.155047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a741e71dfc9'
down_revision: Union[str, Sequence[str], None] = '8c4b376c6ba4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('features') as batch_op:
        batch_op.drop_index('ix_features_name')
        batch_op.create_index('ix_features_name', ['name'], unique=False)
        batch_op.create_unique_constraint('uq_feature_name_store_id', ['name', 'store_id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('features') as batch_op:
        batch_op.drop_constraint('uq_feature_name_store_id', type_='unique')
        batch_op.drop_index('ix_features_name')
        batch_op.create_index('ix_features_name', ['name'], unique=True)
