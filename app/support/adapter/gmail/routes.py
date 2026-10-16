"""Store-scoped Gmail mailbox settings and live activation."""

import asyncio
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.exceptions import RefreshError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.Users import User
from app.dependencies.auth import get_admin_user
from app.dependencies.database import get_db
from app.support.adapter.gmail.client import GmailClient, GmailCredentialsConfig
from app.support.adapter.gmail.models import GmailMailbox
from app.support.adapter.gmail.schemas import (
    CreateGmailMailbox,
    GmailMailboxSettings,
    UpdateGmailMailbox,
)
from app.support.adapter.gmail.settings import gmail_settings
from app.support.adapter.registry import configured_mailboxes

router = APIRouter(prefix="/support/mailboxes/gmail", tags=["support-mailboxes"])


def _store_id(admin: User) -> str:
    if not admin.store_id or not admin.store_id.strip():
        raise HTTPException(status_code=403, detail="Admin token is missing a storeId")
    return admin.store_id.strip()


def _owned(db: Session, address: str, store_id: str) -> GmailMailbox:
    row = db.get(GmailMailbox, address.strip().lower())
    if row is None or row.store_id != store_id:
        raise HTTPException(status_code=404, detail="Gmail mailbox is not configured")
    return row


def _settings(row: GmailMailbox, request: Request) -> GmailMailboxSettings:
    if not row.enabled:
        return GmailMailboxSettings(
            mailbox=row.mailbox,
            enabled=False,
            has_refresh_token=bool(row.refresh_token),
            activation_status="disabled",
        )
    registry = getattr(request.app.state, "support_mailbox_registry", None)
    adapter = registry.get("gmail") if registry else None
    if adapter is None:
        status, error = "unavailable", "Support service is not running"
    else:
        status, error = adapter.activation_status(row.mailbox)
    return GmailMailboxSettings(
        mailbox=row.mailbox,
        enabled=row.enabled,
        has_refresh_token=bool(row.refresh_token),
        activation_status=status,
        activation_error=error,
    )


def _live_adapter(request: Request):
    registry = getattr(request.app.state, "support_mailbox_registry", None)
    adapter = registry.get("gmail") if registry else None
    if adapter is None:
        raise HTTPException(status_code=503, detail="Support service is not running")
    return adapter


async def _verify_account(address: str, refresh_token: str) -> None:
    if not gmail_settings.CLIENT_ID or not gmail_settings.CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Gmail OAuth client is not configured")
    client = GmailClient(
        GmailCredentialsConfig(
            client_id=gmail_settings.CLIENT_ID,
            client_secret=gmail_settings.CLIENT_SECRET,
            refresh_token=refresh_token,
        ),
        user_email=address,
        timeout=gmail_settings.TIMEOUT_SECONDS,
    )
    try:
        authorized_address = await asyncio.to_thread(client.get_profile_email)
    except RefreshError as error:
        raise HTTPException(status_code=422, detail="Gmail refresh token was refused") from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not verify Gmail account") from error
    if authorized_address.strip().lower() != address:
        raise HTTPException(status_code=422, detail="Refresh token belongs to another Gmail account")


@router.get("", response_model=list[GmailMailboxSettings])
def list_gmail_mailboxes(
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[GmailMailboxSettings]:
    rows = db.query(GmailMailbox).filter_by(store_id=_store_id(admin)).order_by(GmailMailbox.mailbox).all()
    return [_settings(row, request) for row in rows]


@router.get("/{mailbox}", response_model=GmailMailboxSettings)
def read_gmail_mailbox(
    mailbox: str,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> GmailMailboxSettings:
    return _settings(_owned(db, mailbox, _store_id(admin)), request)


@router.post("", response_model=GmailMailboxSettings, status_code=201)
async def create_gmail_mailbox(
    payload: CreateGmailMailbox,
    request: Request,
    response: Response,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> GmailMailboxSettings:
    store_id = _store_id(admin)
    adapter = _live_adapter(request)
    existing = db.get(GmailMailbox, payload.mailbox)
    if existing is not None:
        # Seeded rows predate store ownership. A saved token requires proof of
        # knowledge; rows with no token can be configured through this API.
        if existing.store_id is not None or (
            existing.refresh_token is not None
            and not hmac.compare_digest(existing.refresh_token, payload.refresh_token)
        ):
            raise HTTPException(status_code=409, detail="Gmail mailbox address is already configured")
        await _verify_account(existing.mailbox, payload.refresh_token)
        existing.store_id = store_id
        if existing.refresh_token is None:
            existing.refresh_token = payload.refresh_token
        existing.enabled = payload.enabled
        db.commit()
        await adapter.reload_mailbox(db, existing.mailbox)
        response.status_code = 200
        return _settings(existing, request)
    if any(
        key.mailbox == payload.mailbox and key.adapter != "gmail"
        for key in configured_mailboxes(db)
    ):
        raise HTTPException(status_code=409, detail="Mailbox address uses another connection method")
    await _verify_account(payload.mailbox, payload.refresh_token)
    row = GmailMailbox(
        mailbox=payload.mailbox,
        store_id=store_id,
        refresh_token=payload.refresh_token,
        enabled=payload.enabled,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Gmail mailbox address is already configured") from error
    await adapter.reload_mailbox(db, row.mailbox)
    return _settings(row, request)


@router.put("/{mailbox}", response_model=GmailMailboxSettings)
async def update_gmail_mailbox(
    mailbox: str,
    payload: UpdateGmailMailbox,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> GmailMailboxSettings:
    row = _owned(db, mailbox, _store_id(admin))
    adapter = _live_adapter(request)
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        if "refresh_token" in changes:
            await _verify_account(row.mailbox, changes["refresh_token"])
        if changes.get("enabled", row.enabled) and not changes.get(
            "refresh_token", row.refresh_token
        ):
            raise HTTPException(status_code=422, detail="A refresh token is required to enable Gmail")
        for field, value in changes.items():
            setattr(row, field, value)
        db.commit()
        await adapter.reload_mailbox(db, row.mailbox)
    return _settings(row, request)


@router.post("/{mailbox}/disconnect", response_model=GmailMailboxSettings)
async def disconnect_gmail_mailbox(
    mailbox: str,
    request: Request,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> GmailMailboxSettings:
    row = _owned(db, mailbox, _store_id(admin))
    adapter = _live_adapter(request)
    row.refresh_token = None
    row.enabled = False
    db.commit()
    await adapter.reload_mailbox(db, row.mailbox)
    return _settings(row, request)
