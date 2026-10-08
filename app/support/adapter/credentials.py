"""Encrypted credential column for Mailbox Connection tables.

`EncryptedString` stores a Fernet token and hands back the plain text, so adapter models
declare `app_password = Column(EncryptedString, nullable=False)` and never see ciphertext.
The key is `SUPPORT_CREDENTIALS_KEY`, read when a value is written or read rather than at
import, so models import fine without it and only touching a credential fails.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.config.setting import settings


class CredentialsKeyError(RuntimeError):
    """`SUPPORT_CREDENTIALS_KEY` is unset or not a valid Fernet key."""


class CredentialsDecryptError(RuntimeError):
    """A stored credential can't be decrypted: the key differs from the one that wrote
    it, or the stored value is corrupted."""


@lru_cache(maxsize=4)
def _fernet_for(key: str) -> Fernet:
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as error:
        raise CredentialsKeyError(
            "SUPPORT_CREDENTIALS_KEY is not a valid Fernet key (32 url-safe base64-encoded "
            "bytes). Generate one with: poetry run python -c "
            "'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        ) from error


def _fernet() -> Fernet:
    key = settings.SUPPORT_CREDENTIALS_KEY
    if not key:
        raise CredentialsKeyError(
            "SUPPORT_CREDENTIALS_KEY is not set; it is required to read or write "
            "Mailbox Connection credentials. See docs/setup-guide.md."
        )
    return _fernet_for(key)


def encrypt_credential(plain_text: str) -> str:
    return _fernet().encrypt(plain_text.encode()).decode()


def decrypt_credential(token: str) -> str:
    fernet = _fernet()
    try:
        return fernet.decrypt(token.encode()).decode()
    except InvalidToken as error:
        # Never fall back to returning the stored value: it would be sent to a Mail
        # Provider as a password.
        raise CredentialsDecryptError(
            "a stored Mailbox Connection credential could not be decrypted: "
            "SUPPORT_CREDENTIALS_KEY differs from the key that encrypted it, or the "
            "stored value is corrupted"
        ) from error


class EncryptedString(TypeDecorator):
    """A string encrypted at rest with `SUPPORT_CREDENTIALS_KEY`. `None` stays `None`."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_credential(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_credential(value)
