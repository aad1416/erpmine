"""change_user_id_to_string

Revision ID: a1b2c3d4e5f6
Revises: 2a741e71dfc9
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2a741e71dfc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users.id: Integer PK -> String(36) PK
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'id',
            existing_type=sa.Integer(),
            type_=sa.String(36),
            existing_nullable=False,
        )

    # chats.user_id: Integer -> String(36)
    with op.batch_alter_table('chats', schema=None) as batch_op:
        batch_op.alter_column(
            'user_id',
            existing_type=sa.Integer(),
            type_=sa.String(36),
            existing_nullable=False,
        )

    # files.user_id: Integer -> String(36)
    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.alter_column(
            'user_id',
            existing_type=sa.Integer(),
            type_=sa.String(36),
            existing_nullable=True,
        )

    # personas.updated_by_user_id: Integer -> String(36)
    with op.batch_alter_table('personas', schema=None) as batch_op:
        batch_op.alter_column(
            'updated_by_user_id',
            existing_type=sa.Integer(),
            type_=sa.String(36),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('personas', schema=None) as batch_op:
        batch_op.alter_column(
            'updated_by_user_id',
            existing_type=sa.String(36),
            type_=sa.Integer(),
            existing_nullable=False,
        )

    with op.batch_alter_table('files', schema=None) as batch_op:
        batch_op.alter_column(
            'user_id',
            existing_type=sa.String(36),
            type_=sa.Integer(),
            existing_nullable=True,
        )

    with op.batch_alter_table('chats', schema=None) as batch_op:
        batch_op.alter_column(
            'user_id',
            existing_type=sa.String(36),
            type_=sa.Integer(),
            existing_nullable=False,
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'id',
            existing_type=sa.String(36),
            type_=sa.Integer(),
            existing_nullable=False,
        )
