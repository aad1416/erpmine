import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PREVIOUS_HEAD = "b2c3d4e5f6a7"


def _alembic(db_path, *args):
    subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"},
        check=True, capture_output=True,
    )


def test_store_migration_clears_credentials_only_and_enforces_store_ownership(tmp_path):
    db_path = tmp_path / "mailboxes.db"
    _alembic(db_path, "upgrade", PREVIOUS_HEAD)
    with sqlite3.connect(db_path) as db:
        db.execute("INSERT INTO imap_mailboxes (mailbox, app_password) VALUES ('old@shop.com', 'old-secret')")
        db.execute("INSERT INTO imap_outbox (mailbox, external_message_id, normalized_payload, status, captured_at) VALUES ('old@shop.com', 'msg', '{}', 'captured', '2026-01-01')")
        db.execute("INSERT INTO imap_thread_messages (id, adapter, mailbox, conversation_id, direction, sender_address, message_at, created_at) VALUES ('thread', 'imap', 'old@shop.com', 'conversation', 'inbound', 'customer@example.com', '2026-01-01', '2026-01-01')")
        db.execute("INSERT INTO conversations (id, adapter, mailbox, conversation_id, question_round_count, serial_correction_attempt_count, created_at, updated_at) VALUES ('conversation', 'imap', 'old@shop.com', 'conversation', 0, 0, '2026-01-01', '2026-01-01')")
        db.execute("INSERT INTO ingestion_tasks (id, task_type, adapter, mailbox, conversation_id, payload, status, attempt_count, created_at, updated_at) VALUES ('task', 'message', 'imap', 'old@shop.com', 'conversation', '{}', 'open', 0, '2026-01-01', '2026-01-01')")
    _alembic(db_path, "upgrade", "head")
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM imap_mailboxes").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM imap_outbox").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM imap_thread_messages").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM conversations").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM ingestion_tasks").fetchone()[0] == 1
        db.execute("INSERT INTO imap_mailboxes (mailbox, store_id) VALUES ('one@shop.com', 'store-a')")
        try:
            db.execute("INSERT INTO imap_mailboxes (mailbox, store_id) VALUES ('two@shop.com', 'store-a')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("store_id must be unique")
        try:
            db.execute("INSERT INTO imap_mailboxes (mailbox) VALUES ('missing@shop.com')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("store_id must be required")
        try:
            db.execute("INSERT INTO imap_mailboxes (mailbox, store_id) VALUES ('one@shop.com', 'store-b')")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("mailbox must remain unique")
