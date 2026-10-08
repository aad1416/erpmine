"""classroom feature decoupling: add collections table, drop classrooms.feature_id, make documents.feature_id nullable

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-04-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. Create the collections (feature_classroom) table
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feature_id", sa.Integer(), sa.ForeignKey("features.id"), nullable=False),
        sa.Column("classroom_id", sa.String(36), sa.ForeignKey("classrooms.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("feature_id", "classroom_id", name="uq_feature_classroom"),
    )

    # 2. Drop unique constraint on classrooms.feature_id then drop the column
    if is_sqlite:
        # SQLite: rebuild table without feature_id
        op.execute("DROP INDEX IF EXISTS uq_classrooms_feature_id")
        op.execute("""
            CREATE TABLE classrooms_new (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        op.execute("""
            INSERT INTO classrooms_new (id, name, created_at, updated_at)
            SELECT id, name, created_at, updated_at FROM classrooms
        """)
        op.execute("DROP TABLE classrooms")
        op.execute("ALTER TABLE classrooms_new RENAME TO classrooms")
    else:
        op.drop_constraint("uq_classrooms_feature_id", "classrooms", type_="unique")
        op.drop_column("classrooms", "feature_id")

    # 3. Make documents.feature_id nullable
    if is_sqlite:
        op.execute("""
            CREATE TABLE documents_new (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                feature_id INTEGER REFERENCES features(id),
                file_id VARCHAR(36) NOT NULL UNIQUE REFERENCES files(id),
                document_metadata JSON,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        op.execute("""
            INSERT INTO documents_new (id, feature_id, file_id, document_metadata, created_at, updated_at)
            SELECT id, feature_id, file_id, document_metadata, created_at, updated_at FROM documents
        """)
        op.execute("DROP TABLE documents")
        op.execute("ALTER TABLE documents_new RENAME TO documents")
    else:
        op.alter_column("documents", "feature_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 3. Revert documents.feature_id to not nullable (best effort — may fail if NULLs exist)
    if not is_sqlite:
        op.alter_column("documents", "feature_id", existing_type=sa.Integer(), nullable=False)

    # 2. Restore feature_id on classrooms
    if is_sqlite:
        op.execute("""
            CREATE TABLE classrooms_old (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                feature_id INTEGER REFERENCES features(id),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """)
        op.execute("""
            INSERT INTO classrooms_old (id, name, created_at, updated_at)
            SELECT id, name, created_at, updated_at FROM classrooms
        """)
        op.execute("DROP TABLE classrooms")
        op.execute("ALTER TABLE classrooms_old RENAME TO classrooms")
    else:
        op.add_column(
            "classrooms",
            sa.Column("feature_id", sa.Integer(), sa.ForeignKey("features.id"), nullable=True),
        )
        op.create_unique_constraint("uq_classrooms_feature_id", "classrooms", ["feature_id"])

    # 1. Drop collections table
    op.drop_table("collections")
