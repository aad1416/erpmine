"""IMAP/SMTP Mailbox Connection settings (ADR 0002).

`ImapMailboxConfig` is what the IMAP client and SMTP sender connect with; the adapter
builds one from each `imap_mailboxes` row.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.support.adapter.imap.models import (
    GMAIL_IMAP_HOST,
    GMAIL_IMAP_PORT,
    GMAIL_SMTP_HOST,
    GMAIL_SMTP_PORT,
    IMPLICIT_TLS,
)


@dataclass(frozen=True)
class ImapMailboxConfig:
    email: str
    app_password: str
    imap_host: str = GMAIL_IMAP_HOST
    imap_port: int = GMAIL_IMAP_PORT
    imap_tls_mode: str = IMPLICIT_TLS  # "ssl" (implicit TLS) | "starttls"
    smtp_host: str = GMAIL_SMTP_HOST
    smtp_port: int = GMAIL_SMTP_PORT
    smtp_tls_mode: str = IMPLICIT_TLS  # "ssl" (implicit TLS) | "starttls"

