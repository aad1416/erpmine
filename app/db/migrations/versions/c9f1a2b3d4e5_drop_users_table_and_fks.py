"""drop users table and fk constraints

Revision ID: c9f1a2b3d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07

user_id columns on chats, files, and personas are kept as plain strings
so user IDs from the identity provider can still be recorded for audit/tracking.
"""

from alembic import op
import sqlalchemy as sa

revision = "c9f1a2b3d4e5"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # PostgreSQL enforces FKs so they must be dropped before the referenced table
        with op.batch_alter_table("chats") as batch_op:
            batch_op.drop_constraint("chats_user_id_fkey", type_="foreignkey")
        with op.batch_alter_table("files") as batch_op:
            batch_op.drop_constraint("files_user_id_fkey", type_="foreignkey")
        with op.batch_alter_table("personas") as batch_op:
            batch_op.drop_constraint("personas_updated_by_user_id_fkey", type_="foreignkey")

    # SQLite doesn't enforce FKs, so we can drop the table directly
    op.drop_table("users")


def downgrade():
    # Recreate the users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("username", sa.String(), unique=True, nullable=False, index=True),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("user_type", sa.String(), nullable=False, server_default="user"),
    )

    # Restore FK constraints
    with op.batch_alter_table("chats") as batch_op:
        batch_op.create_foreign_key(
            "chats_user_id_fkey", "users", ["user_id"], ["id"]
        )

    with op.batch_alter_table("files") as batch_op:
        batch_op.create_foreign_key(
            "files_user_id_fkey", "users", ["user_id"], ["id"]
        )

    with op.batch_alter_table("personas") as batch_op:
        batch_op.create_foreign_key(
            "personas_updated_by_user_id_fkey", "users", ["updated_by_user_id"], ["id"]
        )
