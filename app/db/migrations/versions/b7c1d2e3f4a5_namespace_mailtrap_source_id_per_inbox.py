"""namespace mailtrap source_id per inbox

Rewrites the flat `source_id = 'mailtrap'` to the composite `mailtrap:<inbox_address>`
that MailtrapAdapter now produces, matching Gmail's `gmail:<email>` convention. Without
this, the adapter cold-starts against a fresh cursor and every in-flight conversation,
task and outbox row is orphaned under the old key.

The target address is the one inbox that was live when the flat id was in use. That
setting was MAILTRAP_INBOX_ADDRESS, since renamed MAILTRAP_INBOX_ADDRESS_1 (same inbox).
Both names are read straight from the environment, not the app settings, which no longer
have either (b2c3d4e5f6a7), so a later rename cannot crash a fresh `upgrade head`. If no
row carries the old id, or no address is set, there is nothing to migrate: no-op.

Revision ID: b7c1d2e3f4a5
Revises: a1b2c3d4e5f7
Create Date: 2026-08-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pydantic_settings import BaseSettings, SettingsConfigDict


# revision identifiers, used by Alembic.
revision: str = 'b7c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_SOURCE_ID = "mailtrap"

# Every table carrying a source_id. adapter_cursors is the load-bearing one (PK — losing
# it means a re-cold-start); the other three are part of unique constraints that the
# rewrite cannot violate, since old and new values never coexist for the same inbox.
_TABLES = (
    "adapter_cursors",
    "adapter_outbox_messages",
    "ingestion_tasks",
    "conversations",
)


class _LegacyMailtrapInbox(BaseSettings):
    """Frozen here: the app settings move on while this migration must not."""

    model_config = SettingsConfigDict(
        extra="ignore", env_file=".env", env_file_encoding="utf-8"
    )

    MAILTRAP_INBOX_ADDRESS_1: str | None = None
    MAILTRAP_INBOX_ADDRESS: str | None = None


def _new_source_id() -> str | None:
    inbox = _LegacyMailtrapInbox()
    # Newest name first.
    address = inbox.MAILTRAP_INBOX_ADDRESS_1 or inbox.MAILTRAP_INBOX_ADDRESS
    if not address:
        return None
    return f"mailtrap:{address.lower()}"


def _rewrite(from_value: str, to_value: str) -> None:
    connection = op.get_bind()
    for table in _TABLES:
        connection.execute(
            sa.text(
                f"UPDATE {table} SET source_id = :to_value WHERE source_id = :from_value"
            ),
            {"to_value": to_value, "from_value": from_value},
        )


def _has_rows(source_id: str) -> bool:
    connection = op.get_bind()
    return any(
        connection.execute(
            sa.text(f"SELECT 1 FROM {table} WHERE source_id = :source_id LIMIT 1"),
            {"source_id": source_id},
        ).first()
        for table in _TABLES
    )


def upgrade() -> None:
    if not _has_rows(_OLD_SOURCE_ID):
        return
    new_source_id = _new_source_id()
    if new_source_id is None:
        return
    _rewrite(_OLD_SOURCE_ID, new_source_id)


def downgrade() -> None:
    new_source_id = _new_source_id()
    if new_source_id is None:
        return
    _rewrite(new_source_id, _OLD_SOURCE_ID)
