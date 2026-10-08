"""EncryptedString through a real table: credentials are ciphertext at rest, plain text
through the ORM, and a missing key, wrong key or corrupted value raises a clear error
instead of handing back garbage."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import Column, String, create_engine, text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.setting import settings
from app.support.adapter.credentials import (
    CredentialsDecryptError,
    CredentialsKeyError,
    EncryptedString,
)

PLAIN_PASSWORD = "app-password-under-test"


class _TestBase(DeclarativeBase):
    pass


class _TestMailbox(_TestBase):
    __tablename__ = "test_encrypted_mailboxes"

    mailbox = Column(String, primary_key=True)
    app_password = Column(EncryptedString, nullable=True)


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
def credentials_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", key)
    return key


def _store(session_factory, app_password=PLAIN_PASSWORD):
    with session_factory() as session:
        session.add(_TestMailbox(mailbox="help@shop.com", app_password=app_password))
        session.commit()


def _load(session_factory):
    with session_factory() as session:
        return session.get(_TestMailbox, "help@shop.com").app_password


def _raw_value(session_factory):
    with session_factory() as session:
        return session.execute(
            text("SELECT app_password FROM test_encrypted_mailboxes")
        ).scalar_one()


def _unwrap(error: BaseException) -> BaseException:
    # SQLAlchemy wraps an exception raised while binding a parameter in StatementError.
    return error.orig if isinstance(error, StatementError) else error


def test_round_trip_stores_ciphertext_and_reads_plain_text(
    session_factory, credentials_key
):
    _store(session_factory)

    raw_value = _raw_value(session_factory)
    assert raw_value != PLAIN_PASSWORD
    assert PLAIN_PASSWORD not in raw_value
    assert _load(session_factory) == PLAIN_PASSWORD


def test_none_stays_none(session_factory, credentials_key):
    _store(session_factory, app_password=None)

    assert _raw_value(session_factory) is None
    assert _load(session_factory) is None


def test_missing_key_raises_on_write(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", None)

    with pytest.raises(Exception) as raised:
        _store(session_factory)

    error = _unwrap(raised.value)
    assert isinstance(error, CredentialsKeyError)
    assert "SUPPORT_CREDENTIALS_KEY is not set" in str(error)


def test_missing_key_raises_on_read(session_factory, credentials_key, monkeypatch):
    _store(session_factory)
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", None)

    with pytest.raises(CredentialsKeyError, match="SUPPORT_CREDENTIALS_KEY is not set"):
        _load(session_factory)


def test_malformed_key_raises(session_factory, monkeypatch):
    monkeypatch.setattr(settings, "SUPPORT_CREDENTIALS_KEY", "not-a-fernet-key")

    with pytest.raises(Exception) as raised:
        _store(session_factory)

    error = _unwrap(raised.value)
    assert isinstance(error, CredentialsKeyError)
    assert "not a valid Fernet key" in str(error)


def test_wrong_key_raises_instead_of_returning_garbage(
    session_factory, credentials_key, monkeypatch
):
    _store(session_factory)
    monkeypatch.setattr(
        settings, "SUPPORT_CREDENTIALS_KEY", Fernet.generate_key().decode()
    )

    with pytest.raises(CredentialsDecryptError, match="could not be decrypted"):
        _load(session_factory)


def test_corrupted_value_raises_instead_of_returning_garbage(
    session_factory, credentials_key
):
    _store(session_factory)
    with session_factory() as session:
        session.execute(
            text("UPDATE test_encrypted_mailboxes SET app_password = :corrupted"),
            {"corrupted": _raw_value(session_factory)[:-6] + "AAAAAA"},
        )
        session.commit()

    with pytest.raises(CredentialsDecryptError, match="could not be decrypted"):
        _load(session_factory)
