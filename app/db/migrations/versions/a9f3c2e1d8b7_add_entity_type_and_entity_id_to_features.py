"""add entity_type and entity_id to features

Revision ID: a9f3c2e1d8b7
Revises: d4e5f6a7b8c9
Create Date: 2026-04-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a9f3c2e1d8b7"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("features", sa.Column("entity_type", sa.String(), nullable=True))
    op.add_column("features", sa.Column("entity_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("features", "entity_id")
    op.drop_column("features", "entity_type")
