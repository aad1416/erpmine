"""classroom item m2m: add classroom_item_assignments, drop classroom_items.classroom_id

Revision ID: d4e5f6a7b8c9
Revises: a3b4c5d6e7f8
Create Date: 2026-04-20

Note on ChromaDB: this migration represents a fresh break for classroom vector
collections. The application now creates one ChromaDB collection per item
(`item_{ClassroomItem.id}`) instead of per classroom (`classroom_{classroom_id}`).
Existing `classroom_{id}` collection directories on disk are left in place but
become unreferenced; an operator can drop them manually from the vector store
persistence directory.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. Create the new join table for M:N classroom ↔ item
    op.create_table(
        "classroom_item_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "classroom_id",
            sa.String(length=36),
            sa.ForeignKey("classrooms.id"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.String(length=36),
            sa.ForeignKey("classroom_items.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("classroom_id", "item_id", name="uq_classroom_item"),
    )

    # 2. Backfill: each existing (classroom_id, item_id) pair becomes one assignment
    op.execute(
        """
        INSERT INTO classroom_item_assignments (classroom_id, item_id, created_at)
        SELECT classroom_id, id, created_at FROM classroom_items
        """
    )

    # 3. Drop classroom_id from classroom_items
    if is_sqlite:
        # SQLite: rebuild the table without classroom_id
        op.execute(
            """
            CREATE TABLE classroom_items_new (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                inventory_item_id VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        op.execute(
            """
            INSERT INTO classroom_items_new (id, inventory_item_id, created_at, updated_at)
            SELECT id, inventory_item_id, created_at, updated_at FROM classroom_items
            """
        )
        op.execute("DROP TABLE classroom_items")
        op.execute("ALTER TABLE classroom_items_new RENAME TO classroom_items")
        op.create_index(
            "ix_classroom_items_id", "classroom_items", ["id"], unique=False
        )
        op.create_index(
            "ix_classroom_items_inventory_item_id",
            "classroom_items",
            ["inventory_item_id"],
            unique=True,
        )
    else:
        op.drop_constraint(
            "classroom_items_classroom_id_fkey",
            "classroom_items",
            type_="foreignkey",
        )
        op.drop_column("classroom_items", "classroom_id")


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. Re-add classroom_id to classroom_items, backfilled from the first assignment
    if is_sqlite:
        op.execute(
            """
            CREATE TABLE classroom_items_old (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                classroom_id VARCHAR(36) NOT NULL REFERENCES classrooms(id),
                inventory_item_id VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        op.execute(
            """
            INSERT INTO classroom_items_old (id, classroom_id, inventory_item_id, created_at, updated_at)
            SELECT
                ci.id,
                (
                    SELECT cia.classroom_id
                    FROM classroom_item_assignments cia
                    WHERE cia.item_id = ci.id
                    ORDER BY cia.id ASC
                    LIMIT 1
                ) AS classroom_id,
                ci.inventory_item_id,
                ci.created_at,
                ci.updated_at
            FROM classroom_items ci
            """
        )
        op.execute("DROP TABLE classroom_items")
        op.execute("ALTER TABLE classroom_items_old RENAME TO classroom_items")
        op.create_index(
            "ix_classroom_items_id", "classroom_items", ["id"], unique=False
        )
        op.create_index(
            "ix_classroom_items_inventory_item_id",
            "classroom_items",
            ["inventory_item_id"],
            unique=True,
        )
    else:
        op.add_column(
            "classroom_items",
            sa.Column(
                "classroom_id",
                sa.String(length=36),
                sa.ForeignKey("classrooms.id"),
                nullable=True,
            ),
        )
        op.execute(
            """
            UPDATE classroom_items ci
            SET classroom_id = (
                SELECT cia.classroom_id
                FROM classroom_item_assignments cia
                WHERE cia.item_id = ci.id
                ORDER BY cia.id ASC
                LIMIT 1
            )
            """
        )
        op.alter_column(
            "classroom_items",
            "classroom_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )

    # 2. Drop the join table
    op.drop_table("classroom_item_assignments")
