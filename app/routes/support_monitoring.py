from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models.Users import User
from app.dependencies.auth import get_admin_user
from app.dependencies.database import get_db
from app.dependencies.lyndom_db import get_lyndom_db
from app.repositories.lyndom_db import LyndomDBRepository
from app.schemas.support_monitoring import (
    ThreadDetail,
    ThreadListResponse,
    ThreadStatus,
)
from app.services import support_monitoring_service
from app.support.adapter.mailbox_key import MailboxKey

router = APIRouter(prefix="/support/monitoring", tags=["support-monitoring"])


@router.get("/threads", response_model=ThreadListResponse)
def list_threads(
    q: Optional[str] = Query(None, description="Filter by sender email (substring match)"),
    adapter: Optional[str] = Query(
        None, description="Filter by Connection Method, e.g. 'imap', 'gmail', 'mailtrap'"
    ),
    mailbox: Optional[str] = Query(None, description="Filter by Mailbox address"),
    status_: Optional[List[ThreadStatus]] = Query(
        None, alias="status", description="Repeatable; threads matching any of these"
    ),
    needs_attention: Optional[bool] = Query(None),
    activity_since: Optional[datetime] = Query(None),
    activity_until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    lyndom_db: LyndomDBRepository = Depends(get_lyndom_db),
) -> ThreadListResponse:
    mailboxes = support_monitoring_service.resolve_store_mailboxes(
        admin_user.store_id, lyndom_db, db
    )
    return support_monitoring_service.list_threads(
        db,
        q=q,
        mailboxes=mailboxes,
        adapter=adapter,
        mailbox=mailbox,
        statuses=status_,
        needs_attention=needs_attention,
        activity_since=activity_since,
        activity_until=activity_until,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/threads/{adapter}/{mailbox}/{conversation_id}", response_model=ThreadDetail
)
def get_thread_detail(
    adapter: str,
    mailbox: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    lyndom_db: LyndomDBRepository = Depends(get_lyndom_db),
) -> ThreadDetail:
    scoped_mailboxes = support_monitoring_service.resolve_store_mailboxes(
        admin_user.store_id, lyndom_db, db
    )
    mailbox_key = MailboxKey.of(adapter, mailbox)
    if mailbox_key not in scoped_mailboxes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    return _thread_detail_or_404(db, mailbox_key, conversation_id)


@router.get(
    "/threads/{source_id}/{conversation_id}",
    response_model=ThreadDetail,
    deprecated=True,
)
def get_thread_detail_by_source_id(
    source_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user),
    lyndom_db: LyndomDBRepository = Depends(get_lyndom_db),
) -> ThreadDetail:
    """Deprecated: use /threads/{adapter}/{mailbox}/{conversation_id}. Kept while the
    monitoring panel outside this repo still builds detail URLs from `source_id`, which
    is no longer stored. Matches the path against the source IDs built from the caller's
    Mailboxes (`MailboxKey.source_id`) rather than splitting it."""
    scoped_mailboxes = support_monitoring_service.resolve_store_mailboxes(
        admin_user.store_id, lyndom_db, db
    )
    mailbox_key = next(
        (
            scoped_mailbox
            for scoped_mailbox in scoped_mailboxes
            if scoped_mailbox.source_id == source_id
        ),
        None,
    )
    if mailbox_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    return _thread_detail_or_404(db, mailbox_key, conversation_id)


def _thread_detail_or_404(
    db: Session, mailbox_key: MailboxKey, conversation_id: str
) -> ThreadDetail:
    detail = support_monitoring_service.get_thread_detail(db, mailbox_key, conversation_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    return detail
