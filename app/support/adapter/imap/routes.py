"""Authenticated store IMAP mailbox settings routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db.models.Users import User
from app.dependencies.auth import get_admin_user
from app.dependencies.database import get_db
from app.support.adapter.imap.mailbox_service import (
    MailboxConflict,
    MailboxIncomplete,
    MailboxNeedsLiveAdapter,
    get_mailbox,
    save_without_live_adapter,
)
from app.support.adapter.imap.adapter import MailboxActivationFailed, MailboxTransitionPending
from app.support.adapter.imap.schemas import ImapMailboxSettings, UpdateImapMailbox
from app.support.adapter.imap.transition_service import (
    acknowledge_backfill_review,
    cancel_address_change,
    latest_transition,
    transition_work,
)

router = APIRouter(prefix="/support/mailboxes/imap", tags=["support-mailboxes"])


def _with_activation(
    settings: ImapMailboxSettings, request: Request, db: Session, store_id: str
) -> ImapMailboxSettings:
    transition = latest_transition(db, store_id)
    settings = settings.model_copy(
        update={"transition": transition_work(db, transition) if transition else None}
    )
    registry = getattr(request.app.state, "support_mailbox_registry", None)
    adapter = registry.get("imap") if registry else None
    if adapter is None:
        return settings.model_copy(
            update={
                "activation_status": "unavailable",
                "activation_error": "Support service is not running",
            }
        )
    status, error = adapter.activation_status(store_id)
    return settings.model_copy(
        update={"activation_status": status, "activation_error": error}
    )


async def _activate(request: Request, db: Session, store_id: str) -> None:
    registry = getattr(request.app.state, "support_mailbox_registry", None)
    adapter = registry.get("imap") if registry else None
    if adapter is not None:
        await adapter.save_and_activate(db, store_id, UpdateImapMailbox())


def _store_id(admin: User) -> str:
    if not admin.store_id or not admin.store_id.strip():
        raise HTTPException(status_code=403, detail="Admin token is missing a storeId")
    return admin.store_id.strip()


@router.get("", response_model=ImapMailboxSettings)
def read_imap_mailbox(
    request: Request, admin: User = Depends(get_admin_user), db: Session = Depends(get_db)
) -> ImapMailboxSettings:
    store_id = _store_id(admin)
    settings = get_mailbox(db, store_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="IMAP mailbox is not configured")
    return _with_activation(settings, request, db, store_id)


@router.put("", response_model=ImapMailboxSettings)
async def save_imap_mailbox(
    request: UpdateImapMailbox,
    http_request: Request,
    response: Response,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> ImapMailboxSettings:
    try:
        store_id = _store_id(admin)
        registry = getattr(http_request.app.state, "support_mailbox_registry", None)
        adapter = registry.get("imap") if registry else None
        if adapter is None:
            settings, created = save_without_live_adapter(db, store_id, request)
        else:
            settings, created = await adapter.save_and_activate(db, store_id, request)
        response.status_code = 201 if created else 200
        return _with_activation(settings, http_request, db, store_id)
    except MailboxConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except MailboxIncomplete as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except MailboxNeedsLiveAdapter as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except MailboxActivationFailed as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except MailboxTransitionPending as error:
        raise HTTPException(
            status_code=409,
            detail={"message": str(error), "transition": error.work.model_dump(mode="json")},
        ) from error


@router.post("/retry", response_model=ImapMailboxSettings)
async def retry_imap_mailbox(
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> ImapMailboxSettings:
    store_id = _store_id(admin)
    settings = get_mailbox(db, store_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="IMAP mailbox is not configured")
    if getattr(request.app.state, "support_mailbox_registry", None) is None:
        raise HTTPException(status_code=503, detail="Support service is not running")
    try:
        await _activate(request, db, store_id)
    except MailboxActivationFailed as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except MailboxConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except MailboxTransitionPending as error:
        raise HTTPException(
            status_code=409,
            detail={"message": str(error), "transition": error.work.model_dump(mode="json")},
        ) from error
    return _with_activation(settings, request, db, store_id)


@router.post("/transition/cancel", response_model=ImapMailboxSettings)
async def cancel_imap_address_change(
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> ImapMailboxSettings:
    store_id = _store_id(admin)
    settings = get_mailbox(db, store_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="IMAP mailbox is not configured")
    registry = getattr(request.app.state, "support_mailbox_registry", None)
    adapter = registry.get("imap") if registry else None
    cancelled = await cancel_address_change(db, store_id, adapter)
    if not cancelled:
        raise HTTPException(status_code=404, detail="No pending IMAP address change")
    return _with_activation(settings, request, db, store_id)


@router.post("/transition/backfill-reviewed", response_model=ImapMailboxSettings)
def mark_imap_backfill_reviewed(
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> ImapMailboxSettings:
    store_id = _store_id(admin)
    settings = get_mailbox(db, store_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="IMAP mailbox is not configured")
    if not acknowledge_backfill_review(db, store_id):
        raise HTTPException(status_code=404, detail="No completed backfill review is pending")
    return _with_activation(settings, request, db, store_id)
