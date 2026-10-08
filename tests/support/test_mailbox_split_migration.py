"""Migration d5e6f7a8b9c0 backfills adapter + mailbox from existing source IDs, and
downgrades cleanly. Runs alembic in a subprocess against a temporary SQLite file, so
env.py's logging config and settings never touch the test process or the real DB."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PREVIOUS_HEAD = "c3d4e5f6a7b8"
# Pinned: later migrations drop tables this one only copies from.
REVISION = "d5e6f7a8b9c0"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic(db_path: Path, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        check=True,
        capture_output=True,
    )


def _seed_old_source_ids(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        for row_id, source_id in (
            ("1", "gmail:Support@Acme.com"),
            ("2", "imap:help@shop.com"),
            ("3", "mailtrap:dev@inbox.mailtrap.io"),
            ("4", "mailtrap"),
        ):
            connection.execute(
                "INSERT INTO ingestion_tasks (id, task_type, source_id, conversation_id, "
                "external_message_id, payload, status, attempt_count, created_at, updated_at) "
                "VALUES (?, 'message', ?, 'c', ?, '{}', 'open', 0, '2026-01-01', '2026-01-01')",
                (row_id, source_id, row_id),
            )
            connection.execute(
                "INSERT INTO conversations (id, source_id, conversation_id, "
                "question_round_count, serial_correction_attempt_count, created_at, updated_at) "
                "VALUES (?, ?, 'c', 0, 0, '2026-01-01', '2026-01-01')",
                (row_id, source_id),
            )
        connection.execute(
            "INSERT INTO imap_thread_messages (id, source_id, conversation_id, direction, "
            "message_id, sender_address, message_at, created_at) "
            "VALUES ('1', 'imap:help@shop.com', 'c', 'inbound', '<a@x>', 'a@x.com', "
            "'2026-01-01', '2026-01-01')"
        )
        connection.execute(
            "INSERT INTO gmail_watches (source_id, updated_at) "
            "VALUES ('gmail:support@acme.com', '2026-01-01')"
        )


def _identities(db_path: Path, table: str) -> dict[str, tuple]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(f"SELECT source_id, adapter, mailbox FROM {table}").fetchall()
    return {source_id: (adapter, mailbox) for source_id, adapter, mailbox in rows}


def _columns(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_backfills_adapter_and_mailbox_and_downgrades(tmp_path):
    db_path = tmp_path / "migration.db"
    _alembic(db_path, "upgrade", PREVIOUS_HEAD)
    _seed_old_source_ids(db_path)

    _alembic(db_path, "upgrade", REVISION)

    expected = {
        "gmail:Support@Acme.com": ("gmail", "support@acme.com"),
        "imap:help@shop.com": ("imap", "help@shop.com"),
        "mailtrap:dev@inbox.mailtrap.io": ("mailtrap", "dev@inbox.mailtrap.io"),
        "mailtrap": (None, None),
    }
    assert _identities(db_path, "ingestion_tasks") == expected
    assert _identities(db_path, "conversations") == expected
    assert _identities(db_path, "imap_thread_messages") == {
        "imap:help@shop.com": ("imap", "help@shop.com")
    }
    assert _identities(db_path, "gmail_watches") == {
        "gmail:support@acme.com": ("gmail", "support@acme.com")
    }

    _alembic(db_path, "downgrade", PREVIOUS_HEAD)

    for table in ("ingestion_tasks", "conversations", "imap_thread_messages", "gmail_watches"):
        assert {"adapter", "mailbox"}.isdisjoint(_columns(db_path, table))
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversations").fetchone() == (4,)


def test_fresh_database_upgrades_to_head(tmp_path):
    _alembic(tmp_path / "fresh.db", "upgrade", "head")
