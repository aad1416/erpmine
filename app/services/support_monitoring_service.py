"""Read-only queries for the support monitoring API (thread list + thread detail).

Thread-level status is derived on every request, not stored — Conversation has no
status column. Task and message rows are joined by the (adapter, mailbox,
conversation_id) natural key rather than a foreign key, matching how the ingestion pipeline itself
correlates them (see app/support/ingestion/task_repository.py). List-view filtering on
the derived status/needs_attention fields happens in Python after fetching, which is
fine at current data volume — see the plan this module implements
(okay-we-need-to-buzzing-journal.md) for why that tradeoff was made deliberately
rather than denormalizing a status column.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config.setting import settings
from app.db.models.Conversation import Conversation
from app.db.models.ConversationMessage import ConversationMessage
from app.repositories.conversations import ConversationRepository
from app.repositories.lyndom_db import LyndomDBRepository
from app.schemas.support_monitoring import (
    MessageTaskSummary,
    ThreadDetail,
    ThreadListResponse,
    ThreadStatus,
    ThreadSummary,
    TicketTaskSummary,
    TimelineEntry,
    TimelineMessageEntry,
    TimelineTaskEntry,
)
from app.support.adapter.mailbox_key import MailboxKey
from app.support.adapter.registry import configured_mailboxes
from app.support.ingestion.models import IngestionTask, TaskStatus, TaskType
from app.support.ingestion.task_repository import ConversationKey, TaskRepository

_BODY_PREVIEW_LEN = 200
_PENDING_TASK_STATUSES = (TaskStatus.open.value, TaskStatus.running.value)


def resolve_store_mailboxes(
    store_id: str, lyndom_db: LyndomDBRepository, db: Session
) -> list[MailboxKey]:
    """Maps an admin's store to the Mailbox(es) they're scoped to.

    Still hardwired to every Mailbox in the Mailbox Adapters' tables (the real per-store
    lookup below stays commented out) rather than the store's own Mailbox.
    """
    # email = lyndom_db.get_store_email(store_id) if store_id else None
    # if not email:
    #     raise HTTPException(
    #         status.HTTP_503_SERVICE_UNAVAILABLE,
    #         detail="Store support inbox is not configured",
    #     )
    mailboxes = configured_mailboxes(db)
    if not mailboxes:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Store support inbox is not configured",
        )
    return mailboxes


def derive_status(
    conversation: Conversation,
    tasks: list[IngestionTask],
    latest_message_direction: Optional[str] = None,
) -> tuple[ThreadStatus, bool]:
    """First match wins: ticketed > escalated > in_progress > awaiting_customer > new.
    needs_attention is independent of status — any dead_letter task (including the
    never-executed synthesized escalation marker) sets it, so a real pipeline failure
    stays visible even on an otherwise-ticketed thread."""
    needs_attention = any(t.status == TaskStatus.dead_letter.value for t in tasks)

    if conversation.ticket_id:
        return ThreadStatus.ticketed, needs_attention

    capped = (
        conversation.question_round_count >= settings.SUPPORT_QUESTION_ROUND_CAP
        or conversation.serial_correction_attempt_count
        >= settings.SUPPORT_SERIAL_CORRECTION_CAP
    ) and not conversation.unit_serial
    has_dead_letter_create_ticket = any(
        t.task_type == TaskType.create_ticket.value
        and t.status == TaskStatus.dead_letter.value
        for t in tasks
    )
    if capped or has_dead_letter_create_ticket:
        return ThreadStatus.escalated, needs_attention

    if any(t.status in _PENDING_TASK_STATUSES for t in tasks):
        return ThreadStatus.in_progress, needs_attention

    if latest_message_direction == "outbound":
        return ThreadStatus.awaiting_customer, needs_attention

    return ThreadStatus.new, needs_attention


def _truncate(text: Optional[str], length: int = _BODY_PREVIEW_LEN) -> Optional[str]:
    if text is None:
        return None
    return text if len(text) <= length else text[: length - 1] + "…"


def _build_message_entry(message: ConversationMessage) -> TimelineMessageEntry:
    return TimelineMessageEntry(
        id=message.id,
        direction=message.direction,
        sender_address=message.sender_address,
        body_text=message.body_text,
        external_message_id=message.external_message_id,
        received_at=message.received_at,
        synced_to_ticket_log=message.synced_to_ticket_log,
    )


def _build_task_entry(task: IngestionTask) -> TimelineTaskEntry:
    payload = task.payload or {}
    entry = TimelineTaskEntry(
        id=task.id,
        task_type=task.task_type,
        status=task.status,
        attempt_count=task.attempt_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
        heartbeat_at=task.heartbeat_at,
        last_error=payload.get("last_error"),
        dead_letter_reason=payload.get("reason"),
    )
    if task.task_type == TaskType.message.value:
        entry.message_summary = MessageTaskSummary(
            sender_address=payload.get("sender_address"),
            sender_name=payload.get("sender_name"),
            subject=payload.get("subject"),
            body_preview=_truncate(payload.get("body_text")),
            external_message_id=payload.get("external_message_id"),
        )
    elif task.task_type == TaskType.create_ticket.value:
        entry.ticket_args = TicketTaskSummary(
            unit_serial=payload.get("unit_serial"),
            issue_description=payload.get("issue_description"),
            title=payload.get("title"),
            customer_message=payload.get("customer_message"),
        )
    elif task.task_type == TaskType.send_message.value:
        entry.outbound_text = payload.get("text")
    return entry


def get_thread_detail(
    db: Session, mailbox_key: MailboxKey, conversation_id: str
) -> Optional[ThreadDetail]:
    conversation = ConversationRepository(db).find(mailbox_key, conversation_id)
    if conversation is None:
        return None

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.received_at.asc())
        .all()
    )
    tasks = TaskRepository(db).list_for_conversation(mailbox_key, conversation_id)

    latest_direction = messages[-1].direction if messages else None
    status, needs_attention = derive_status(conversation, tasks, latest_direction)

    timeline: list[tuple[datetime, TimelineEntry]] = [
        (m.received_at, _build_message_entry(m)) for m in messages
    ] + [(t.created_at, _build_task_entry(t)) for t in tasks]
    timeline.sort(key=lambda item: item[0])

    return ThreadDetail(
        adapter=conversation.adapter,
        mailbox=conversation.mailbox,
        source_id=_deprecated_source_id(conversation),
        conversation_id=conversation.conversation_id,
        unit_serial=conversation.unit_serial,
        issue_description=conversation.issue_description,
        ticket_id=conversation.ticket_id,
        question_round_count=conversation.question_round_count,
        serial_correction_attempt_count=conversation.serial_correction_attempt_count,
        status=status,
        needs_attention=needs_attention,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        timeline=[entry for _, entry in timeline],
    )


def list_threads(
    db: Session,
    *,
    q: Optional[str] = None,
    mailboxes: Optional[list[MailboxKey]] = None,
    adapter: Optional[str] = None,
    mailbox: Optional[str] = None,
    statuses: Optional[list[ThreadStatus]] = None,
    needs_attention: Optional[bool] = None,
    activity_since: Optional[datetime] = None,
    activity_until: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> ThreadListResponse:
    """`mailboxes` scopes the list to the caller's Mailboxes; `adapter` and `mailbox`
    narrow it further, to one Connection Method or one Mailbox address."""
    query = db.query(Conversation)
    if mailboxes:
        query = query.filter(
            or_(
                *(
                    and_(
                        Conversation.adapter == mailbox_key.adapter,
                        Conversation.mailbox == mailbox_key.mailbox,
                    )
                    for mailbox_key in mailboxes
                )
            )
        )
    if adapter:
        query = query.filter(Conversation.adapter == adapter)
    if mailbox:
        query = query.filter(Conversation.mailbox == mailbox.lower())
    if q:
        matching_conversation_ids = (
            db.query(ConversationMessage.conversation_id)
            .filter(ConversationMessage.sender_address.ilike(f"%{q}%"))
            .distinct()
        )
        query = query.filter(Conversation.id.in_(matching_conversation_ids))

    conversations = query.all()
    if not conversations:
        return ThreadListResponse(items=[], total=0, limit=limit, offset=offset)

    conversation_ids = [c.id for c in conversations]
    keys = [_conversation_key(conversation) for conversation in conversations]

    messages_by_conversation: dict[str, list[ConversationMessage]] = defaultdict(list)
    for message in (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id.in_(conversation_ids))
        .order_by(ConversationMessage.received_at.asc())
        .all()
    ):
        messages_by_conversation[message.conversation_id].append(message)

    tasks_by_key: dict[ConversationKey, list[IngestionTask]] = defaultdict(list)
    for task in TaskRepository(db).list_for_conversations(keys):
        tasks_by_key[(task.adapter, task.mailbox, task.conversation_id)].append(task)

    summaries: list[ThreadSummary] = []
    for conversation in conversations:
        messages = messages_by_conversation.get(conversation.id, [])
        tasks = tasks_by_key.get(_conversation_key(conversation), [])
        latest_direction = messages[-1].direction if messages else None
        status, thread_needs_attention = derive_status(
            conversation, tasks, latest_direction
        )

        last_activity_at = (
            messages[-1].received_at if messages else conversation.updated_at
        )
        if activity_since and last_activity_at < activity_since:
            continue
        if activity_until and last_activity_at > activity_until:
            continue
        if statuses and status not in statuses:
            continue
        if needs_attention is not None and thread_needs_attention != needs_attention:
            continue

        inbound_messages = [m for m in messages if m.direction == "inbound"]
        sender_address = (
            inbound_messages[-1].sender_address
            if inbound_messages
            else (messages[-1].sender_address if messages else None)
        )

        summaries.append(
            ThreadSummary(
                adapter=conversation.adapter,
                mailbox=conversation.mailbox,
                source_id=_deprecated_source_id(conversation),
                conversation_id=conversation.conversation_id,
                sender_address=sender_address,
                unit_serial=conversation.unit_serial,
                ticket_id=conversation.ticket_id,
                status=status,
                needs_attention=thread_needs_attention,
                last_activity_at=last_activity_at,
                message_count=len(messages),
                open_task_count=sum(
                    1 for t in tasks if t.status in _PENDING_TASK_STATUSES
                ),
                dead_letter_task_count=sum(
                    1 for t in tasks if t.status == TaskStatus.dead_letter.value
                ),
            )
        )

    summaries.sort(key=lambda s: s.last_activity_at, reverse=True)
    total = len(summaries)
    page = summaries[offset : offset + limit]
    return ThreadListResponse(items=page, total=total, limit=limit, offset=offset)


def _deprecated_source_id(conversation: Conversation) -> str:
    """Deprecated `source_id` response field, built from adapter + mailbox since nothing
    stores it: the monitoring panel outside this repo still reads it."""
    return MailboxKey(conversation.adapter, conversation.mailbox).source_id


def _conversation_key(conversation: Conversation) -> ConversationKey:
    return (conversation.adapter, conversation.mailbox, conversation.conversation_id)
