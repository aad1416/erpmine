"""Store-scoped IMAP settings persistence; activation is handled by the adapter."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, defer

from app.support.adapter.imap.models import ImapMailbox
from app.support.adapter.imap.schemas import (
    CreateImapMailbox,
    ImapMailboxSettings,
    UpdateImapMailbox,
)
from app.support.adapter.registry import configured_mailboxes
from app.support.adapter.imap.transition_service import address_owned_by_other_store

_CONNECTION_FIELDS = (
    "mailbox",
    "app_password",
    "imap_host",
    "imap_port",
    "imap_tls_mode",
    "smtp_host",
    "smtp_port",
    "smtp_tls_mode",
)


class MailboxConflict(Exception):
    pass


class MailboxIncomplete(Exception):
    pass


class MailboxNeedsLiveAdapter(Exception):
    pass


def save_without_live_adapter(
    db: Session, store_id: str, request: UpdateImapMailbox
) -> tuple[ImapMailboxSettings, bool]:
    """Persist safe edits while polling is stopped; an address change must wait."""
    row = db.query(ImapMailbox.mailbox).filter_by(store_id=store_id).scalar()
    if row is not None and request.mailbox is not None and request.mailbox != row:
        preview_mailbox(db, store_id, request)
        raise MailboxNeedsLiveAdapter(
            "Support service must be running to change an IMAP address safely"
        )
    return save_mailbox(db, store_id, request)


def _validate_change(
    db: Session, row: ImapMailbox | None, changes: dict, store_id: str
) -> bool:
    """Apply the same first-save and address checks for preview and persistence."""
    if row is None:
        missing = [field for field in ("mailbox", "app_password") if field not in changes]
        if missing:
            raise MailboxIncomplete(f"Required on first save: {', '.join(missing)}")
    new_address = changes.get("mailbox")
    address_changed = new_address is not None and (row is None or new_address != row.mailbox)
    if address_changed:
        if any(key.mailbox == new_address for key in configured_mailboxes(db)):
            raise MailboxConflict("Mailbox address is already configured")
        if address_owned_by_other_store(db, new_address, store_id):
            raise MailboxConflict("Mailbox address belongs to another store's support history")
    return address_changed


def get_mailbox(db: Session, store_id: str) -> ImapMailboxSettings | None:
    row = _public_query(db).filter(ImapMailbox.store_id == store_id).one_or_none()
    return _settings(row) if row else None


def save_mailbox(
    db: Session,
    store_id: str,
    request: UpdateImapMailbox,
    *,
    initial_cursor: str | None = None,
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
    # Inspect addresses before mutating this row or autoflushing it.
    address_changed = _validate_change(db, row, changes, store_id)
    if created:
        defaults_and_changes = CreateImapMailbox.model_validate(changes).model_dump()
        row = ImapMailbox(store_id=store_id, **defaults_and_changes)
        row.cursor = initial_cursor
        db.add(row)
    else:
        if address_changed:
            row.cursor = initial_cursor
        elif row.cursor is None and initial_cursor is not None:
            row.cursor = initial_cursor
        for field, value in changes.items():
            setattr(row, field, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise MailboxConflict("Store or mailbox address is already configured") from error
    return get_mailbox(db, store_id), created


def preview_mailbox(db: Session, store_id: str, request: UpdateImapMailbox) -> ImapMailbox:
    """Build a detached candidate without changing the saved, working connection."""
    row = db.query(ImapMailbox).filter_by(store_id=store_id).one_or_none()
    changes = request.model_dump(exclude_unset=True)
    address_changed = _validate_change(db, row, changes, store_id)
    if row is None:
        values = CreateImapMailbox.model_validate(changes).model_dump()
    else:
        values = {field: getattr(row, field) for field in _CONNECTION_FIELDS}
        values.update(changes)
    return ImapMailbox(
        store_id=store_id,
        cursor=row.cursor if row is not None and not address_changed else None,
        **values,
    )


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
