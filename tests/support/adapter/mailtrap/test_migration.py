"""Migration e7f8a9b0c1d2 creates the Mailtrap tables and carries over each Mailtrap
inbox's cursor from `adapter_cursors` and each Conversation's newest message from the
shared outbox. Runs alembic in a subprocess against a temporary SQLite file, never the
real DB."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PREVIOUS_HEAD = "d5e6f7a8b9c0"
# Pinned: later migrations drop tables this one only copies from.
REVISION = "e7f8a9b0c1d2"
REPO_ROOT = Path(__file__).resolve().parents[4]


def _alembic(db_path: Path, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        check=True,
        capture_output=True,
    )


def _outbox_row(row_id, source_id, conversation_id, external_message_id, received_at):
    payload = json.dumps({"received_at": received_at})
    return (row_id, source_id, external_message_id, conversation_id, payload)


def _seed_old_state(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            "INSERT INTO adapter_cursors (source_id, cursor_value, updated_at) "
            "VALUES (?, ?, '2026-01-01')",
            [
                ("mailtrap:First@Inbound-Mailtrap.io", "2024-01-05T00:00:00+00:00"),
                ("mailtrap:second@inbound-mailtrap.io", "2024-01-06T00:00:00+00:00"),
                ("mailtrap", "2023-01-01T00:00:00+00:00"),
                ("gmail:support@acme.com", "12345"),
            ],
        )
        connection.executemany(
            "INSERT INTO adapter_outbox_messages (id, source_id, external_message_id, "
            "conversation_id, normalized_payload, captured_at, status) "
            "VALUES (?, ?, ?, ?, ?, '2026-01-01', 'published')",
            [
                _outbox_row("1", "mailtrap:first@inbound-mailtrap.io", "t1", "older", "2024-01-02T00:00:00Z"),
                _outbox_row("2", "mailtrap:first@inbound-mailtrap.io", "t1", "newer", "2024-01-03T00:00:00Z"),
                _outbox_row("3", "mailtrap:first@inbound-mailtrap.io", "t2", "t2-only", "2024-01-01T00:00:00Z"),
                _outbox_row("4", "gmail:support@acme.com", "t1", "gmail-msg", "2024-01-09T00:00:00Z"),
            ],
        )


def _query(db_path: Path, sql: str) -> set[tuple]:
    with sqlite3.connect(db_path) as connection:
        return set(connection.execute(sql).fetchall())


def test_copies_mailtrap_cursors_and_reply_targets_and_downgrades(tmp_path):
    db_path = tmp_path / "migration.db"
    _alembic(db_path, "upgrade", PREVIOUS_HEAD)
    _seed_old_state(db_path)

    _alembic(db_path, "upgrade", REVISION)

    assert _query(db_path, "SELECT mailbox, inbox_id, api_token, cursor FROM mailtrap_mailboxes") == {
        ("first@inbound-mailtrap.io", None, None, "2024-01-05T00:00:00+00:00"),
        ("second@inbound-mailtrap.io", None, None, "2024-01-06T00:00:00+00:00"),
    }
    assert _query(
        db_path,
        "SELECT mailbox, conversation_id, external_message_id "
        "FROM mailtrap_last_inbound_messages",
    ) == {
        ("first@inbound-mailtrap.io", "t1", "newer"),
        ("first@inbound-mailtrap.io", "t2", "t2-only"),
    }
    # Copied, not moved: the shared cursor stays until it is dropped.
    assert len(_query(db_path, "SELECT source_id FROM adapter_cursors")) == 4

    _alembic(db_path, "downgrade", PREVIOUS_HEAD)

    tables = _query(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'")
    assert not {("mailtrap_mailboxes",), ("mailtrap_last_inbound_messages",)} & tables


def test_fresh_database_upgrades_to_head(tmp_path):
    db_path = tmp_path / "fresh.db"
    _alembic(db_path, "upgrade", "head")

    assert _query(db_path, "SELECT mailbox FROM mailtrap_mailboxes") == set()
