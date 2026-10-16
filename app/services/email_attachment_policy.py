"""Metadata rules shared by capture, AI access, and ticket delivery."""

from __future__ import annotations

from pathlib import Path

from app.config.email_attachments import (
    ALLOWED_EMAIL_EXTENSIONS, DANGEROUS_EXTENSIONS, MAX_ATTACHMENTS_PER_EMAIL,
    MAX_EMAIL_ATTACHMENTS_SIZE_BYTES, MAX_FILENAME_CHARACTERS, MAX_FILE_SIZE_BYTES,
)


def safe_file_name(value: str) -> str:
    # Path.name does not treat a Windows backslash as a separator on Linux.
    return (value or "").replace("\\", "/").rsplit("/", 1)[-1]


def metadata_rejection(
    *, file_name: str, position: int, declared_size: int,
    message_bytes_already_accepted: int,
) -> str | None:
    if position >= MAX_ATTACHMENTS_PER_EMAIL:
        return f"An email can contain at most {MAX_ATTACHMENTS_PER_EMAIL} attachments."
    if not file_name or len(file_name) > MAX_FILENAME_CHARACTERS or any(
        ord(character) < 32 for character in file_name
    ):
        return "The attachment filename is invalid."
    extension = Path(file_name).suffix.lower().lstrip(".")
    if extension in DANGEROUS_EXTENSIONS:
        return "This executable or active-code file type is blocked for safety."
    if extension not in ALLOWED_EMAIL_EXTENSIONS:
        return "This file type is not accepted for email attachments."
    if declared_size > MAX_FILE_SIZE_BYTES:
        return "The attachment exceeds the 20 MiB per-file limit."
    if (
        declared_size
        and message_bytes_already_accepted + declared_size
        > MAX_EMAIL_ATTACHMENTS_SIZE_BYTES
    ):
        return "The email exceeds the 25 MiB combined attachment limit."
    return None


def stored_file_rejection(file_name: str, size: int) -> str | None:
    """Apply current metadata policy to a file captured under an older policy."""
    return metadata_rejection(
        file_name=safe_file_name(file_name), position=0, declared_size=size,
        message_bytes_already_accepted=0,
    )
