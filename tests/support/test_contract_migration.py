"""Migration b2c3d4e5f6a7 drops source_id and the shared adapter tables, makes adapter +
mailbox NOT NULL, resolves the legacy rows left with NULLs, and gives stored message
payloads adapter + mailbox. Runs alembic in a subprocess against a temporary SQLite
file, so env.py's logging config and settings never touch the test process or the real
DB."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.support.adapter.schemas import NormalizedMessage

PREVIOUS_HEAD = "a0b1c2d3e4f5"
REVISION = "b2c3d4e5f6a7"
REPO_ROOT = Path(__file__).resolve().parents[2]

_SUPPORT_TABLES = ("ingestion_tasks", "conversations", "imap_thread_messages", "gmail_watches")


def _alembic(db_path: Path, *args: str, legacy_mailtrap_address: str = "") -> None:
    """Both address names are passed explicitly, so a developer's .env can't decide
    whether the flat `mailtrap` rows are backfilled."""
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": f"sqlite:///{db_path}",
            "MAILTRAP_INBOX_ADDRESS_1": legacy_mailtrap_address,
            "MAILTRAP_INBOX_ADDRESS": "",
        },
        check=True,
        capture_output=True,
    )


def _legacy_payload(source_id: str, external_message_id: str) -> str:
    """A NormalizedMessage stored before messages carried adapter + mailbox."""
    return json.dumps(
        {
            "source_id": source_id,
            "conversation_id": "thread-1",
            "external_message_id": external_message_id,
            "sender_address": "jane@example.com",
            "sender_name": None,
            "received_at": "2026-01-01T09:00:00Z",
            "body_text": "My unit is broken.",
            "subject": "Help",
            "has_attachments": False,
        }
    )


def _seed_previous_head(db_path: Path) -> None:
    """Realistic rows at the previous head: routable ones for every adapter, and the
    flat `mailtrap` rows d5e6f7a8b9c0 left with NULL adapter/mailbox."""
    timestamp = "2026-01-01 09:00:00"
    with sqlite3.connect(db_path) as connection:
        for task_id, task_type, source_id, adapter, mailbox, payload, external_id in (
            ("task-imap", "message", "imap:help@shop.com", "imap", "help@shop.com",
             _legacy_payload("imap:help@shop.com", "m-imap"), "m-imap"),
            ("task-reply", "send_message", "imap:help@shop.com", "imap", "help@shop.com",
             json.dumps({"text": "Thanks"}), None),
            ("task-gmail", "message", "gmail:support@acme.com", "gmail", "support@acme.com",
             json.dumps({**json.loads(_legacy_payload("gmail:support@acme.com", "m-gmail")),
                         "adapter": "gmail", "mailbox": "support@acme.com"}), "m-gmail"),
            ("task-flat", "message", "mailtrap", None, None,
             _legacy_payload("mailtrap", "m-flat"), "m-flat"),
        ):
            connection.execute(
                "INSERT INTO ingestion_tasks (id, task_type, source_id, adapter, mailbox, "
                "conversation_id, external_message_id, payload, status, attempt_count, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'thread-1', ?, ?, 'open', 0, ?, ?)",
                (task_id, task_type, source_id, adapter, mailbox, external_id, payload,
                 timestamp, timestamp),
            )
        for conversation_id, source_id, adapter, mailbox in (
            ("conv-imap", "imap:help@shop.com", "imap", "help@shop.com"),
            ("conv-flat", "mailtrap", None, None),
        ):
            connection.execute(
                "INSERT INTO conversations (id, source_id, adapter, mailbox, conversation_id, "
                "question_round_count, serial_correction_attempt_count, ticket_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 'thread-1', 0, 0, 'tk-1', ?, ?)",
                (conversation_id, source_id, adapter, mailbox, timestamp, timestamp),
            )
            message_id = f"{conversation_id}-message"
            connection.execute(
                "INSERT INTO conversation_messages (id, conversation_id, external_message_id, "
                "sender_address, direction, body_text, received_at, synced_to_ticket_log, "
                "created_at) VALUES (?, ?, 'm1', 'jane@example.com', 'inbound', 'help', ?, 0, ?)",
                (message_id, conversation_id, timestamp, timestamp),
            )
            connection.execute(
                "INSERT INTO pending_log_syncs (id, ticket_id, conversation_message_id, "
                "attempt_count, next_attempt_at, status, created_at, updated_at) "
                "VALUES (?, 'tk-1', ?, 0, ?, 'pending', ?, ?)",
                (f"{conversation_id}-sync", message_id, timestamp, timestamp, timestamp),
            )
        connection.execute(
            "INSERT INTO imap_thread_messages (id, source_id, adapter, mailbox, conversation_id, "
            "direction, message_id, sender_address, message_at, created_at) "
            "VALUES ('thread-row', 'imap:help@shop.com', 'imap', 'help@shop.com', 'thread-1', "
            "'inbound', '<m1@example.com>', 'jane@example.com', ?, ?)",
            (timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO gmail_watches (source_id, adapter, mailbox, history_id, updated_at) "
            "VALUES ('gmail:support@acme.com', 'gmail', 'support@acme.com', '100', ?)",
            (timestamp,),
        )
        for outbox, mailbox, source_id in (
            ("imap_outbox", "help@shop.com", "imap:help@shop.com"),
            ("gmail_outbox", "support@acme.com", "gmail:support@acme.com"),
        ):
            connection.execute(
                f"INSERT INTO {outbox} (mailbox, external_message_id, normalized_payload, "
                "status, captured_at) VALUES (?, 'm-captured', ?, 'captured', ?)",
                (mailbox, _legacy_payload(source_id, "m-captured"), timestamp),
            )
        connection.execute(
            "INSERT INTO adapter_cursors (source_id, cursor_value, updated_at) "
            "VALUES ('imap:help@shop.com', '7:42', ?)",
            (timestamp,),
        )
        connection.execute(
            "INSERT INTO adapter_outbox_messages (id, source_id, external_message_id, "
            "conversation_id, normalized_payload, captured_at, status) "
            "VALUES ('outbox-1', 'imap:help@shop.com', 'm-imap', 'thread-1', ?, ?, 'published')",
            (_legacy_payload("imap:help@shop.com", "m-imap"), timestamp),
        )


def _query(db_path: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(sql).fetchall()


def _columns(db_path: Path, table: str) -> dict[str, dict]:
    with sqlite3.connect(db_path) as connection:
        return {
            name: {"not_null": bool(not_null), "primary_key": primary_key}
            for _, name, _, not_null, _, primary_key in connection.execute(
                f"PRAGMA table_info({table})"
            )
        }


def _tables(db_path: Path) -> set[str]:
    return {name for (name,) in _query(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'")}


@pytest.fixture()
def seeded_db(tmp_path) -> Path:
    db_path = tmp_path / "migration.db"
    _alembic(db_path, "upgrade", PREVIOUS_HEAD)
    _seed_previous_head(db_path)
    return db_path


def test_drops_source_id_and_the_shared_tables_and_deletes_unroutable_rows(seeded_db):
    _alembic(seeded_db, "upgrade", REVISION)

    for table in _SUPPORT_TABLES:
        columns = _columns(seeded_db, table)
        assert "source_id" not in columns
        assert columns["adapter"]["not_null"] and columns["mailbox"]["not_null"]
    watch_columns = _columns(seeded_db, "gmail_watches")
    assert (watch_columns["adapter"]["primary_key"], watch_columns["mailbox"]["primary_key"]) == (1, 2)
    assert not {"adapter_outbox_messages", "adapter_cursors"} & _tables(seeded_db)

    # Routable rows are kept; the flat `mailtrap` ones, with no address to backfill
    # from, are deleted with the Conversation's messages and pending log syncs.
    assert {row[0] for row in _query(seeded_db, "SELECT id FROM ingestion_tasks")} == {
        "task-imap", "task-reply", "task-gmail",
    }
    assert _query(seeded_db, "SELECT id, adapter, mailbox FROM conversations") == [
        ("conv-imap", "imap", "help@shop.com")
    ]
    assert _query(seeded_db, "SELECT id FROM conversation_messages") == [("conv-imap-message",)]
    assert _query(seeded_db, "SELECT id FROM pending_log_syncs") == [("conv-imap-sync",)]
    assert _query(seeded_db, "SELECT adapter, mailbox, history_id FROM gmail_watches") == [
        ("gmail", "support@acme.com", "100")
    ]
    assert _query(seeded_db, "SELECT adapter, mailbox FROM imap_thread_messages") == [
        ("imap", "help@shop.com")
    ]

    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(seeded_db) as connection:
            connection.execute(
                "INSERT INTO conversations (id, conversation_id, question_round_count, "
                "serial_correction_attempt_count, created_at, updated_at) "
                "VALUES ('null-key', 't', 0, 0, '2026-01-01', '2026-01-01')"
            )


def test_stored_message_payloads_get_adapter_and_mailbox(seeded_db):
    _alembic(seeded_db, "upgrade", REVISION)

    payloads = [
        payload
        for (payload,) in _query(
            seeded_db,
            "SELECT payload FROM ingestion_tasks WHERE task_type = 'message' "
            "UNION ALL SELECT normalized_payload FROM imap_outbox "
            "UNION ALL SELECT normalized_payload FROM gmail_outbox",
        )
    ]
    messages = [NormalizedMessage.model_validate(json.loads(payload)) for payload in payloads]
    assert sorted((message.adapter, message.mailbox) for message in messages) == [
        ("gmail", "support@acme.com"),
        ("gmail", "support@acme.com"),
        ("imap", "help@shop.com"),
        ("imap", "help@shop.com"),
    ]
    [(reply_payload,)] = _query(
        seeded_db, "SELECT payload FROM ingestion_tasks WHERE task_type = 'send_message'"
    )
    assert json.loads(reply_payload) == {"text": "Thanks"}


def test_flat_mailtrap_rows_are_backfilled_when_the_inbox_address_is_set(seeded_db):
    _alembic(
        seeded_db, "upgrade", REVISION, legacy_mailtrap_address="Support@Inbound-Mailtrap.io"
    )

    assert _query(seeded_db, "SELECT adapter, mailbox FROM ingestion_tasks WHERE id = 'task-flat'") == [
        ("mailtrap", "support@inbound-mailtrap.io")
    ]
    assert _query(seeded_db, "SELECT adapter, mailbox FROM conversations WHERE id = 'conv-flat'") == [
        ("mailtrap", "support@inbound-mailtrap.io")
    ]
    assert len(_query(seeded_db, "SELECT id FROM pending_log_syncs")) == 2
    [(payload,)] = _query(seeded_db, "SELECT payload FROM ingestion_tasks WHERE id = 'task-flat'")
    assert NormalizedMessage.model_validate(json.loads(payload)).mailbox == (
        "support@inbound-mailtrap.io"
    )


def test_downgrade_restores_source_id_and_the_shared_tables(seeded_db):
    _alembic(seeded_db, "upgrade", REVISION)
    _alembic(seeded_db, "downgrade", PREVIOUS_HEAD)

    for table in _SUPPORT_TABLES:
        columns = _columns(seeded_db, table)
        assert columns["source_id"]["not_null"]
        assert not columns["adapter"]["not_null"]
    assert _columns(seeded_db, "gmail_watches")["source_id"]["primary_key"] == 1
    assert {"adapter_outbox_messages", "adapter_cursors"} <= _tables(seeded_db)
    assert _query(seeded_db, "SELECT source_id FROM conversations") == [("imap:help@shop.com",)]
    assert _query(seeded_db, "SELECT source_id FROM gmail_watches") == [("gmail:support@acme.com",)]

    _alembic(seeded_db, "upgrade", "head")


def test_fresh_database_upgrades_to_head(tmp_path):
    db_path = tmp_path / "fresh.db"
    _alembic(db_path, "upgrade", "head")

    assert "source_id" not in _columns(db_path, "ingestion_tasks")
