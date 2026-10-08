"""Migration a0b1c2d3e4f5 creates the Gmail API tables and carries over each Gmail
Mailbox's history cursor from `adapter_cursors` and its not-yet-ingested messages from
the shared outbox. Runs alembic in a subprocess against a temporary SQLite file, never
the real DB."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

PREVIOUS_HEAD = "f8a9b0c1d2e3"
# Pinned: later migrations drop tables this one only copies from.
REVISION = "a0b1c2d3e4f5"
REPO_ROOT = Path(__file__).resolve().parents[4]


def _alembic(db_path: Path, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        check=True,
        capture_output=True,
    )


def _outbox_row(row_id, source_id, external_message_id, status, captured_at):
    payload = json.dumps({"source_id": source_id, "external_message_id": external_message_id})
    return (row_id, source_id, external_message_id, "t1", payload, captured_at, status)


def _seed_old_state(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            "INSERT INTO adapter_cursors (source_id, cursor_value, updated_at) "
            "VALUES (?, ?, '2026-01-01')",
            [
                ("gmail:Support@Acme-Store.com", "12345"),
                ("gmail:sales@acme-store.com", "678"),
                ("imap:support@acme-store.com", "7:42"),
                ("mailtrap:dev@inbound-mailtrap.io", "2024-01-05T00:00:00+00:00"),
            ],
        )
        connection.executemany(
            "INSERT INTO adapter_outbox_messages (id, source_id, external_message_id, "
            "conversation_id, normalized_payload, captured_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                _outbox_row("1", "gmail:support@acme-store.com", "newer", "captured", "2026-01-02"),
                _outbox_row("2", "gmail:Support@Acme-Store.com", "older", "captured", "2026-01-01"),
                _outbox_row("3", "gmail:support@acme-store.com", "done", "published", "2026-01-01"),
                _outbox_row("4", "imap:support@acme-store.com", "imap-msg", "captured", "2026-01-01"),
            ],
        )


def _query(db_path: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(sql).fetchall()


def test_copies_gmail_cursors_and_undelivered_messages_and_downgrades(tmp_path):
    db_path = tmp_path / "migration.db"
    _alembic(db_path, "upgrade", PREVIOUS_HEAD)
    _seed_old_state(db_path)

    _alembic(db_path, "upgrade", REVISION)

    assert set(_query(db_path, "SELECT mailbox, refresh_token, history_id FROM gmail_mailboxes")) == {
        ("support@acme-store.com", None, "12345"),
        ("sales@acme-store.com", None, "678"),
    }
    # Oldest first, undelivered, and only the captured Gmail rows.
    assert _query(
        db_path,
        "SELECT mailbox, external_message_id, status FROM gmail_outbox ORDER BY id",
    ) == [
        ("support@acme-store.com", "older", "captured"),
        ("support@acme-store.com", "newer", "captured"),
    ]
    [(payload,)] = _query(
        db_path, "SELECT normalized_payload FROM gmail_outbox WHERE external_message_id = 'newer'"
    )
    assert json.loads(payload)["source_id"] == "gmail:support@acme-store.com"
    # Copied, not moved: the shared tables stay until they are dropped.
    assert len(_query(db_path, "SELECT source_id FROM adapter_cursors")) == 4
    assert len(_query(db_path, "SELECT id FROM adapter_outbox_messages")) == 4

    _alembic(db_path, "downgrade", PREVIOUS_HEAD)

    tables = set(_query(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'"))
    assert not {("gmail_mailboxes",), ("gmail_outbox",), ("gmail_sent_replies",)} & tables
    assert ("gmail_watches",) in tables


def test_fresh_database_upgrades_to_head(tmp_path):
    db_path = tmp_path / "fresh.db"
    _alembic(db_path, "upgrade", "head")

    assert _query(db_path, "SELECT mailbox FROM gmail_mailboxes") == []
    assert _query(db_path, "SELECT id FROM gmail_outbox") == []
    assert _query(db_path, "SELECT idempotency_key FROM gmail_sent_replies") == []
