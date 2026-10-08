"""Store-scoped IMAP connection persistence. The running adapter is a startup snapshot."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer

from app.support.adapter.imap.models import ImapMailbox
from app.support.adapter.imap.schemas import (
    CreateImapMailbox,
    ImapMailboxSettings,
    UpdateImapMailbox,
)
from app.support.adapter.registry import configured_mailboxes


class MailboxConflict(Exception):
    pass


class MailboxIncomplete(Exception):
    pass


def get_mailbox(db: Session, store_id: str) -> ImapMailboxSettings | None:
    row = _public_query(db).filter(ImapMailbox.store_id == store_id).one_or_none()
    return _settings(row) if row else None


def save_mailbox(
    db: Session, store_id: str, request: UpdateImapMailbox
) -> tuple[ImapMailboxSettings, bool]:
    # Defer the encrypted column: an update that omits the password must never
    # decrypt or re-encrypt it, including when only server settings change.
    row = (
        db.query(ImapMailbox)
        .options(defer(ImapMailbox.app_password))
        .filter_by(store_id=store_id)
        .one_or_none()
    )
    changes = request.model_dump(exclude_unset=True)
    created = row is None
    new_address = changes.get("mailbox")
    address_changed = new_address is not None and (created or new_address != row.mailbox)
    if address_changed:
        # Inspect addresses only, before mutating this row or autoflushing it.
        if any(key.mailbox == new_address for key in configured_mailboxes(db)):
            raise MailboxConflict("Mailbox address is already configured")
    if created:
        missing = [field for field in ("mailbox", "app_password") if field not in changes]
        if missing:
            raise MailboxIncomplete(f"Required on first save: {', '.join(missing)}")
        defaults_and_changes = CreateImapMailbox.model_validate(changes).model_dump()
        row = ImapMailbox(store_id=store_id, **defaults_and_changes)
        db.add(row)
    else:
        if address_changed:
            row.cursor = None
        for field, value in changes.items():
            setattr(row, field, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise MailboxConflict("Store or mailbox address is already configured") from error
    return get_mailbox(db, store_id), created


def _public_query(db: Session):
    # Never load or decrypt the credential or poll cursor for the settings response.
    return db.query(
        ImapMailbox.mailbox,
        ImapMailbox.imap_host,
        ImapMailbox.imap_port,
        ImapMailbox.imap_tls_mode,
        ImapMailbox.smtp_host,
        ImapMailbox.smtp_port,
        ImapMailbox.smtp_tls_mode,
    )


def _settings(row) -> ImapMailboxSettings:
    return ImapMailboxSettings(
        mailbox=row.mailbox,
        imap_host=row.imap_host,
        imap_port=row.imap_port,
        imap_tls_mode=row.imap_tls_mode,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_tls_mode=row.smtp_tls_mode,
    )
