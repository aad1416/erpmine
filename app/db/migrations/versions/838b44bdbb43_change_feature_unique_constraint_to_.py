"""change_feature_unique_constraint_to_entity_id_store_id

Revision ID: 838b44bdbb43
Revises: a9f3c2e1d8b7
Create Date: 2026-05-02 20:29:46.727920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '838b44bdbb43'
down_revision: Union[str, Sequence[str], None] = 'a9f3c2e1d8b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite can't drop table-level constraints — must recreate the table.
        # Avoid batch_alter_table because it reflects FK chains and trips on the
        # already-dropped `users` table. Use raw DDL instead.
        op.execute("""
            CREATE TABLE features_new (
                id      INTEGER NOT NULL,
                name    VARCHAR,
                store_id VARCHAR,
                persona_id INTEGER,
                entity_type VARCHAR,
                entity_id VARCHAR,
                PRIMARY KEY (id),
                CONSTRAINT fk_features_persona_id FOREIGN KEY (persona_id) REFERENCES personas (id),
                CONSTRAINT uq_feature_entity_id_store_id UNIQUE (entity_id, store_id)
            )
        """)
        op.execute("INSERT INTO features_new SELECT id, name, store_id, persona_id, entity_type, entity_id FROM features")
        op.execute("DROP TABLE features")
        op.execute("ALTER TABLE features_new RENAME TO features")
        op.execute("CREATE INDEX ix_features_id ON features (id)")
        op.execute("CREATE INDEX ix_features_name ON features (name)")
    else:
        with op.batch_alter_table("features") as batch_op:
            batch_op.drop_constraint("uq_feature_name_store_id", type_="unique")
            batch_op.create_unique_constraint(
                "uq_feature_entity_id_store_id", ["entity_id", "store_id"]
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("""
            CREATE TABLE features_new (
                id      INTEGER NOT NULL,
                name    VARCHAR,
                store_id VARCHAR,
                persona_id INTEGER,
                entity_type VARCHAR,
                entity_id VARCHAR,
                PRIMARY KEY (id),
                CONSTRAINT fk_features_persona_id FOREIGN KEY (persona_id) REFERENCES personas (id),
                CONSTRAINT uq_feature_name_store_id UNIQUE (name, store_id)
            )
        """)
        op.execute("INSERT INTO features_new SELECT id, name, store_id, persona_id, entity_type, entity_id FROM features")
        op.execute("DROP TABLE features")
        op.execute("ALTER TABLE features_new RENAME TO features")
        op.execute("CREATE INDEX ix_features_id ON features (id)")
        op.execute("CREATE INDEX ix_features_name ON features (name)")
    else:
        with op.batch_alter_table("features") as batch_op:
            batch_op.drop_constraint("uq_feature_entity_id_store_id", type_="unique")
            batch_op.create_unique_constraint(
                "uq_feature_name_store_id", ["name", "store_id"]
            )
