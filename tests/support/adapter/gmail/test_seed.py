"""The Gmail seeder copies the env-configured Mailbox (`GMAIL_USER_EMAIL`,
`GMAIL_REFRESH_TOKEN`) into `gmail_mailboxes` through the seed script, without printing
the refresh token and without touching the adapter's history cursor."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import sessionmaker

from app.config.setting import settings
from app.support.adapter.gmail.models import GmailMailbox
from app.support.adapter.gmail.seed import GmailSeedSettings, seed_gmail_mailboxes
from app.support.adapter.seeding import discover_seeders
from scripts.seed_support_mailboxes import main as seed_main

REFRESH_TOKEN = "gmail-refresh-token-to-seed"


@pytest.fixture()
def gmail_env(monkeypatch, seed_env):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    seed_env(
        GmailSeedSettings,
        {"GMAIL_USER_EMAIL": "Support@Acme-Store.com", "GMAIL_REFRESH_TOKEN": REFRESH_TOKEN},
    )


def _run(db_session, capsys) -> str:
    seed_main(
        [],
        session_factory=sessionmaker(bind=db_session.get_bind()),
        seeders={"gmail": seed_gmail_mailboxes},
    )
    output = capsys.readouterr().out
    assert REFRESH_TOKEN not in output
    return output


def _rows(db_session) -> dict[str, tuple]:
    db_session.expire_all()
    return {
        row.mailbox: (row.refresh_token, row.history_id)
        for row in db_session.query(GmailMailbox).all()
    }


def test_the_gmail_seeder_is_discovered():
    assert discover_seeders()["gmail"] is seed_gmail_mailboxes


def test_seeding_inserts_the_mailbox_with_an_encrypted_refresh_token(
    gmail_env, db_session, capsys
):
    output = _run(db_session, capsys)

    assert _rows(db_session) == {"support@acme-store.com": (REFRESH_TOKEN, None)}
    assert "inserted: gmail support@acme-store.com" in output
    stored_tokens = db_session.get_bind().connect().exec_driver_sql(
        "SELECT refresh_token FROM gmail_mailboxes"
    ).scalars().all()
    assert REFRESH_TOKEN not in stored_tokens


def test_reseeding_fills_in_a_migrated_row_and_keeps_its_cursor(gmail_env, db_session, capsys):
    # As the migration leaves it: the history cursor, no refresh token yet.
    db_session.add(GmailMailbox(mailbox="support@acme-store.com", history_id="12345"))
    db_session.commit()

    output = _run(db_session, capsys)

    assert _rows(db_session) == {"support@acme-store.com": (REFRESH_TOKEN, "12345")}
    assert "updated: gmail support@acme-store.com" in output
    assert "unchanged:" in _run(db_session, capsys)


def test_a_mailbox_without_a_refresh_token_in_the_env_keeps_its_stored_one(
    gmail_env, db_session, capsys, seed_env
):
    _run(db_session, capsys)
    seed_env(GmailSeedSettings, {"GMAIL_REFRESH_TOKEN": None})

    assert "unchanged: gmail support@acme-store.com" in _run(db_session, capsys)
    assert _rows(db_session) == {"support@acme-store.com": (REFRESH_TOKEN, None)}


def test_an_unset_mailbox_is_not_seeded(gmail_env, db_session, capsys, seed_env):
    seed_env(GmailSeedSettings, {"GMAIL_USER_EMAIL": None})

    _run(db_session, capsys)

    assert _rows(db_session) == {}
