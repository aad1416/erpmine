"""unique classroom feature_id (1:1 classroom per feature)

Revision ID: f1a2b3c4d5e6
Revises: 96c3562d3680
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "96c3562d3680"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Avoid batch_alter_table on SQLite: it reflects FK chains and can fail if a
    # referenced table (e.g. dropped `users`) is missing from the DB.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_classrooms_feature_id "
            "ON classrooms (feature_id)"
        )
    else:
        op.create_unique_constraint(
            "uq_classrooms_feature_id",
            "classrooms",
            ["feature_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP INDEX IF EXISTS uq_classrooms_feature_id")
    else:
        op.drop_constraint(
            "uq_classrooms_feature_id",
            "classrooms",
            type_="unique",
        )
