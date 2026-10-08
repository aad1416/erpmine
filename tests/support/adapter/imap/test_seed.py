"""The IMAP seeder copies the env-configured Mailbox (`IMAP_MAILBOX_*`, `IMAP_*`,
`SMTP_*`) into `imap_mailboxes` through the seed script, without printing the app
password and without touching the adapter's cursor."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import sessionmaker

from app.config.setting import settings
from app.support.adapter.imap.models import ImapMailbox
from app.support.adapter.imap.seed import ImapSeedSettings, seed_imap_mailboxes
from app.support.adapter.seeding import discover_seeders
from scripts.seed_support_mailboxes import main as seed_main

APP_PASSWORD = "imap-app-password-under-test"
GMAIL_SERVERS = ("imap.gmail.com", 993, "ssl", "smtp.gmail.com", 465, "ssl")


@pytest.fixture()
def imap_env(monkeypatch, seed_env):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    seed_env(ImapSeedSettings, {
        "IMAP_MAILBOX_EMAIL": "Support@Acme-Store.com",
        "IMAP_MAILBOX_STORE_ID": "store-a",
        "IMAP_MAILBOX_APP_PASSWORD": APP_PASSWORD,
        "IMAP_HOST": None,
        "IMAP_PORT": None,
        "IMAP_TLS_MODE": None,
        "SMTP_HOST": None,
        "SMTP_PORT": None,
        "SMTP_TLS_MODE": None,
    })


def _run(db_session, capsys) -> str:
    seed_main(
        [],
        session_factory=sessionmaker(bind=db_session.get_bind()),
        seeders={"imap": seed_imap_mailboxes},
    )
    output = capsys.readouterr().out
    assert APP_PASSWORD not in output
    return output


def _rows(db_session) -> dict[str, tuple]:
    db_session.expire_all()
    return {
        row.mailbox: (
            row.app_password,
            row.imap_host,
            row.imap_port,
            row.imap_tls_mode,
            row.smtp_host,
            row.smtp_port,
            row.smtp_tls_mode,
            row.cursor,
        )
        for row in db_session.query(ImapMailbox).all()
    }


def test_the_imap_seeder_is_discovered():
    assert discover_seeders()["imap"] is seed_imap_mailboxes


def test_seeding_inserts_the_mailbox_with_gmail_servers_and_an_encrypted_password(
    imap_env, db_session, capsys
):
    output = _run(db_session, capsys)

    assert _rows(db_session) == {
        "support@acme-store.com": (APP_PASSWORD, *GMAIL_SERVERS, None),
    }
    assert "inserted: imap support@acme-store.com" in output
    stored_passwords = db_session.get_bind().connect().exec_driver_sql(
        "SELECT app_password FROM imap_mailboxes"
    ).scalars().all()
    assert APP_PASSWORD not in stored_passwords


def test_seeding_copies_another_mail_providers_servers(imap_env, db_session, capsys, seed_env):
    seed_env(ImapSeedSettings, {
        "IMAP_HOST": "imap.fastmail.com",
        "IMAP_PORT": 143,
        "IMAP_TLS_MODE": "starttls",
        "SMTP_HOST": "smtp.fastmail.com",
        "SMTP_PORT": 587,
        "SMTP_TLS_MODE": "starttls",
    })

    _run(db_session, capsys)

    assert _rows(db_session)["support@acme-store.com"][1:7] == (
        "imap.fastmail.com", 143, "starttls", "smtp.fastmail.com", 587, "starttls",
    )


def test_reseeding_fills_in_a_migrated_row_and_keeps_its_cursor(imap_env, db_session, capsys):
    # As the migration leaves it: the cursor and Gmail's servers, no app password yet.
    db_session.add(ImapMailbox(mailbox="support@acme-store.com", store_id="store-a", cursor="7:42"))
    db_session.commit()

    output = _run(db_session, capsys)

    assert _rows(db_session)["support@acme-store.com"] == (APP_PASSWORD, *GMAIL_SERVERS, "7:42")
    assert "updated: imap support@acme-store.com" in output
    assert "unchanged:" in _run(db_session, capsys)


def test_an_unset_mailbox_is_not_seeded(imap_env, db_session, capsys, seed_env):
    seed_env(ImapSeedSettings, {"IMAP_MAILBOX_EMAIL": None})

    _run(db_session, capsys)

    assert _rows(db_session) == {}
