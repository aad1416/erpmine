"""Public store mailbox settings. Credentials and polling state are write-only/internal."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.support.adapter.imap.models import (
    GMAIL_IMAP_HOST,
    GMAIL_IMAP_PORT,
    GMAIL_SMTP_HOST,
    GMAIL_SMTP_PORT,
)


class CreateImapMailbox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mailbox: str
    app_password: str = Field(min_length=1)
    imap_host: str = Field(default=GMAIL_IMAP_HOST, min_length=1)
    imap_port: int = Field(default=GMAIL_IMAP_PORT, ge=1, le=65535)
    imap_tls_mode: Literal["ssl", "starttls"] = "ssl"
    smtp_host: str = Field(default=GMAIL_SMTP_HOST, min_length=1)
    smtp_port: int = Field(default=GMAIL_SMTP_PORT, ge=1, le=65535)
    smtp_tls_mode: Literal["ssl", "starttls"] = "ssl"

    @field_validator("mailbox")
    @classmethod
    def valid_mailbox(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or "@" not in value or any(char.isspace() for char in value):
            raise ValueError("mailbox must be an email address")
        return value

    @field_validator("app_password")
    @classmethod
    def nonblank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("imap_host", "smtp_host")
    @classmethod
    def nonblank_host(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class UpdateImapMailbox(CreateImapMailbox):
    """Sparse PUT body. Omission retains a value; explicit null is invalid."""

    mailbox: str | None = None
    app_password: str | None = None
    imap_host: str | None = None
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    imap_tls_mode: Literal["ssl", "starttls"] | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_tls_mode: Literal["ssl", "starttls"] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for field in cls.model_fields:
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null; omit it to retain the saved value")
        return value


class ImapMailboxSettings(BaseModel):
    mailbox: str
    imap_host: str
    imap_port: int
    imap_tls_mode: Literal["ssl", "starttls"]
    smtp_host: str
    smtp_port: int
    smtp_tls_mode: Literal["ssl", "starttls"]
    restart_required: bool = True
