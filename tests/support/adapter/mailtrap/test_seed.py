"""The Mailtrap seeder copies the `MAILTRAP_*_1` / `_2` inboxes into
`mailtrap_mailboxes` through the seed script, without printing a token and without
touching the adapter's cursor."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.orm import sessionmaker

from app.config.setting import settings
from app.support.adapter.mailtrap.models import MailtrapMailbox
from app.support.adapter.mailtrap.seed import MailtrapSeedSettings, seed_mailtrap_mailboxes
from app.support.adapter.seeding import discover_seeders
from scripts.seed_support_mailboxes import main as seed_main

FIRST_TOKEN = "first-mailtrap-token-under-test"
SECOND_TOKEN = "second-mailtrap-token-under-test"


@pytest.fixture()
def mailtrap_env(monkeypatch, seed_env):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode())
    seed_env(MailtrapSeedSettings, {
        "MAILTRAP_INBOX_ADDRESS_1": "First@Inbound-Mailtrap.io",
        "MAILTRAP_INBOX_ID_1": "816",
        "MAILTRAP_API_TOKEN_1": FIRST_TOKEN,
        "MAILTRAP_INBOX_ADDRESS_2": "second@inbound-mailtrap.io",
        "MAILTRAP_INBOX_ID_2": "2551",
        "MAILTRAP_API_TOKEN_2": SECOND_TOKEN,
    })


def _run(db_session, capsys) -> str:
    seed_main(
        [],
        session_factory=sessionmaker(bind=db_session.get_bind()),
        seeders={"mailtrap": seed_mailtrap_mailboxes},
    )
    output = capsys.readouterr().out
    assert FIRST_TOKEN not in output
    assert SECOND_TOKEN not in output
    return output


def _rows(db_session) -> dict[str, tuple]:
    db_session.expire_all()
    return {
        row.mailbox: (row.inbox_id, row.api_token, row.cursor)
        for row in db_session.query(MailtrapMailbox).all()
    }


def test_the_mailtrap_seeder_is_discovered():
    assert discover_seeders()["mailtrap"] is seed_mailtrap_mailboxes


def test_seeding_inserts_both_inboxes_with_encrypted_tokens(mailtrap_env, db_session, capsys):
    output = _run(db_session, capsys)

    assert _rows(db_session) == {
        "first@inbound-mailtrap.io": ("816", FIRST_TOKEN, None),
        "second@inbound-mailtrap.io": ("2551", SECOND_TOKEN, None),
    }
    assert "inserted: mailtrap first@inbound-mailtrap.io" in output
    stored_tokens = db_session.get_bind().connect().exec_driver_sql(
        "SELECT api_token FROM mailtrap_mailboxes"
    ).scalars().all()
    assert FIRST_TOKEN not in stored_tokens
    assert SECOND_TOKEN not in stored_tokens


def test_reseeding_fills_in_a_migrated_row_and_keeps_its_cursor(
    mailtrap_env, db_session, capsys
):
    # As the migration leaves it: the cursor, no credentials yet.
    db_session.add(MailtrapMailbox(mailbox="first@inbound-mailtrap.io", cursor="2024-01-01"))
    db_session.commit()

    output = _run(db_session, capsys)

    assert _rows(db_session)["first@inbound-mailtrap.io"] == ("816", FIRST_TOKEN, "2024-01-01")
    assert "updated: mailtrap first@inbound-mailtrap.io" in output
    assert "unchanged:" in _run(db_session, capsys)


def test_an_unset_inbox_is_not_seeded(mailtrap_env, db_session, capsys, seed_env):
    seed_env(MailtrapSeedSettings, {"MAILTRAP_INBOX_ADDRESS_2": None})

    _run(db_session, capsys)

    assert set(_rows(db_session)) == {"first@inbound-mailtrap.io"}
