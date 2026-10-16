"""Gmail mailbox API payloads. Refresh tokens are write-only."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CreateGmailMailbox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mailbox: str
    refresh_token: str = Field(min_length=1)
    enabled: bool = True

    @field_validator("mailbox")
    @classmethod
    def valid_mailbox(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or "@" not in value or any(char.isspace() for char in value):
            raise ValueError("mailbox must be an email address")
        return value

    @field_validator("refresh_token")
    @classmethod
    def nonblank_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("refresh_token must not be blank")
        return value


class UpdateGmailMailbox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null(cls, value):
        if isinstance(value, dict):
            for field in ("refresh_token", "enabled"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null; omit it to retain the saved value")
        return value

    @field_validator("refresh_token")
    @classmethod
    def nonblank_token(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("refresh_token must not be blank")
        return value


class GmailMailboxSettings(BaseModel):
    mailbox: str
    enabled: bool
    has_refresh_token: bool
    activation_status: str
    activation_error: str | None = None
