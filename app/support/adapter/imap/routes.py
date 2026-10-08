"""Authenticated store IMAP mailbox settings routes."""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.models.Users import User
from app.dependencies.auth import get_admin_user
from app.dependencies.database import get_db
from app.support.adapter.imap.mailbox_service import (
    MailboxConflict,
    MailboxIncomplete,
    get_mailbox,
    save_mailbox,
)
from app.support.adapter.imap.schemas import ImapMailboxSettings, UpdateImapMailbox

router = APIRouter(prefix="/support/mailboxes/imap", tags=["support-mailboxes"])


def _store_id(admin: User) -> str:
    if not admin.store_id or not admin.store_id.strip():
        raise HTTPException(status_code=403, detail="Admin token is missing a storeId")
    return admin.store_id.strip()


@router.get("", response_model=ImapMailboxSettings)
def read_imap_mailbox(
    admin: User = Depends(get_admin_user), db: Session = Depends(get_db)
) -> ImapMailboxSettings:
    settings = get_mailbox(db, _store_id(admin))
    if settings is None:
        raise HTTPException(status_code=404, detail="IMAP mailbox is not configured")
    return settings


@router.put("", response_model=ImapMailboxSettings)
def save_imap_mailbox(
    request: UpdateImapMailbox,
    response: Response,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> ImapMailboxSettings:
    try:
        settings, created = save_mailbox(db, _store_id(admin), request)
        response.status_code = 201 if created else 200
        return settings
    except MailboxConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except MailboxIncomplete as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
