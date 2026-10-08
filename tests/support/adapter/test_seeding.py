"""The Mailbox seed script with a fake seeder: it inserts the seeded rows, a second run
changes nothing, a changed value updates the row without touching columns the seeder
doesn't set, dry-run writes nothing, and nothing it prints contains a credential."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import Column, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.setting import settings
from app.support.adapter import seeding
from app.support.adapter.credentials import EncryptedString
from scripts.seed_support_mailboxes import main as seed_main

FIRST_MAILBOX = "help@shop.com"
SECOND_MAILBOX = "sales@shop.com"


class _TestBase(DeclarativeBase):
    pass


class _FakeMailbox(_TestBase):
    __tablename__ = "fake_seeded_mailboxes"

    mailbox = Column(String, primary_key=True)
    host = Column(String, nullable=False)
    app_password = Column(EncryptedString, nullable=False)
    cursor = Column(Integer, nullable=True)


class _FakeEnv:
    """Stands in for an adapter's settings, read by the fake seeder on every run."""

    def __init__(self):
        self.passwords = {
            FIRST_MAILBOX: "first-password-under-test",
            SECOND_MAILBOX: "second-password-under-test",
        }
        self.host = "imap.shop.com"

    def seed(self) -> list[_FakeMailbox]:
        return [
            _FakeMailbox(mailbox=mailbox, host=self.host, app_password=password)
            for mailbox, password in self.passwords.items()
        ]


@pytest.fixture(autouse=True)
def credentials_key(monkeypatch):
    monkeypatch.setattr(
        settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode()
    )


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _TestBase.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def fake_env():
    return _FakeEnv()


def _run(session_factory, fake_env, capsys, *argv) -> str:
    seed_main(list(argv), session_factory=session_factory, seeders={"fake": fake_env.seed})
    output = capsys.readouterr().out
    for password in fake_env.passwords.values():
        assert password not in output
    return output


def _rows(session_factory) -> dict[str, tuple[str, str, int | None]]:
    with session_factory() as session:
        return {
            row.mailbox: (row.host, row.app_password, row.cursor)
            for row in session.scalars(select(_FakeMailbox))
        }


def test_first_run_inserts_every_seeded_row(session_factory, fake_env, capsys):
    output = _run(session_factory, fake_env, capsys)

    assert _rows(session_factory) == {
        FIRST_MAILBOX: ("imap.shop.com", "first-password-under-test", None),
        SECOND_MAILBOX: ("imap.shop.com", "second-password-under-test", None),
    }
    assert f"inserted: fake {FIRST_MAILBOX}" in output
    assert f"inserted: fake {SECOND_MAILBOX}" in output


def test_second_run_changes_nothing(session_factory, fake_env, capsys):
    _run(session_factory, fake_env, capsys)
    rows_after_first_run = _rows(session_factory)

    output = _run(session_factory, fake_env, capsys)

    assert _rows(session_factory) == rows_after_first_run
    assert "inserted:" not in output
    assert "updated:" not in output
    assert f"unchanged: fake {FIRST_MAILBOX}" in output


def test_changed_value_updates_row_and_keeps_unseeded_columns(
    session_factory, fake_env, capsys
):
    _run(session_factory, fake_env, capsys)
    with session_factory() as session:
        session.get(_FakeMailbox, FIRST_MAILBOX).cursor = 42
        session.commit()
    fake_env.passwords[FIRST_MAILBOX] = "rotated-password-under-test"

    output = _run(session_factory, fake_env, capsys)

    assert _rows(session_factory)[FIRST_MAILBOX] == (
        "imap.shop.com",
        "rotated-password-under-test",
        42,
    )
    assert f"updated: fake {FIRST_MAILBOX}" in output
    assert f"unchanged: fake {SECOND_MAILBOX}" in output


def test_dry_run_writes_nothing(session_factory, fake_env, capsys):
    output = _run(session_factory, fake_env, capsys, "--dry-run")

    assert _rows(session_factory) == {}
    assert f"[dry run] inserted: fake {FIRST_MAILBOX}" in output


def test_dry_run_does_not_apply_updates(session_factory, fake_env, capsys):
    _run(session_factory, fake_env, capsys)
    fake_env.host = "imap.elsewhere.com"

    output = _run(session_factory, fake_env, capsys, "--dry-run")

    assert _rows(session_factory)[FIRST_MAILBOX][0] == "imap.shop.com"
    assert f"[dry run] updated: fake {FIRST_MAILBOX}" in output


def test_no_seeders_prints_nothing_to_seed(session_factory, capsys):
    seed_main([], session_factory=session_factory, seeders={})

    assert "nothing to seed" in capsys.readouterr().out


def test_discovery_imports_each_adapter_folders_seed_module(tmp_path, monkeypatch):
    package = tmp_path / "fake_adapter_package"
    for folder in ("with_seed", "without_seed"):
        (package / folder).mkdir(parents=True)
        (package / folder / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "with_seed" / "seed.py").write_text(
        "from app.support.adapter.seeding import seeder\n"
        "\n"
        "@seeder('with_seed')\n"
        "def seed_with_seed():\n"
        "    return []\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(seeding, "_seeders", {})
    import fake_adapter_package

    monkeypatch.setattr(seeding, "adapter_package", fake_adapter_package)

    assert list(seeding.discover_seeders()) == ["with_seed"]


def test_duplicate_seeder_name_is_rejected(monkeypatch):
    monkeypatch.setattr(seeding, "_seeders", {})
    seeding.seeder("fake")(lambda: [])

    with pytest.raises(ValueError, match="already registered"):
        seeding.seeder("fake")(lambda: [])
