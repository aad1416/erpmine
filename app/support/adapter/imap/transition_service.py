"""Durable IMAP address change windows and admin-visible work summaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.support.adapter.imap.models import (
    ImapAddressTransition,
    ImapOutboxMessage,
    ImapOutboxStatus,
    ImapSentReply,
    ImapSentReplyStatus,
)
from app.support.adapter.imap.schemas import ImapTransitionWork
from app.support.adapter.mailbox_key import MailboxKey
from app.support.ingestion.models import IngestionTask, TaskStatus, TaskType
from app.support.ingestion.task_repository import TaskRepository


def waiting_transition(
    db: Session, store_id: str, previous_mailbox: str, new_mailbox: str
) -> ImapAddressTransition | None:
    return db.query(ImapAddressTransition).filter_by(
        store_id=store_id,
        previous_mailbox=previous_mailbox,
        new_mailbox=new_mailbox,
        status="waiting",
    ).order_by(ImapAddressTransition.id.desc()).first()


def begin_transition(
    db: Session,
    store_id: str,
    previous_mailbox: str,
    new_mailbox: str,
    started_at: datetime,
) -> ImapAddressTransition:
    existing = waiting_transition(db, store_id, previous_mailbox, new_mailbox)
    if existing is not None:
        return existing
    db.query(ImapAddressTransition).filter_by(store_id=store_id, status="waiting").update(
        {ImapAddressTransition.status: "cancelled"}, synchronize_session=False
    )
    transition = ImapAddressTransition(
        store_id=store_id,
        previous_mailbox=previous_mailbox,
        new_mailbox=new_mailbox,
        started_at=started_at,
        status="waiting",
    )
    db.add(transition)
    db.commit()
    return transition


def cancel_transition(db: Session, store_id: str) -> bool:
    changed = db.query(ImapAddressTransition).filter_by(
        store_id=store_id, status="waiting"
    ).update({ImapAddressTransition.status: "cancelled"}, synchronize_session=False)
    if changed:
        db.commit()
    return bool(changed)


class _TransitionCanceller(Protocol):
    async def cancel_address_change(self, db: Session, store_id: str) -> bool: ...


async def cancel_address_change(
    db: Session, store_id: str, adapter: _TransitionCanceller | None
) -> bool:
    """Serialize cancellation with a running adapter's activation when available."""
    if adapter is not None:
        return await adapter.cancel_address_change(db, store_id)
    return cancel_transition(db, store_id)


def latest_transition(db: Session, store_id: str) -> ImapAddressTransition | None:
    return db.query(ImapAddressTransition).filter(
        ImapAddressTransition.store_id == store_id,
        ImapAddressTransition.status.in_(("waiting", "completed")),
    ).order_by(ImapAddressTransition.id.desc()).first()


def acknowledge_backfill_review(db: Session, store_id: str) -> bool:
    """Acknowledge the completed transition's backfill and reply warnings."""
    transition = latest_transition(db, store_id)
    if transition is None or transition.status != "completed" or transition.reviewed_at is not None:
        return False
    work = transition_work(db, transition)
    if not (
        work.backfill_review_required
        or work.dead_letter_reply_count
        or work.unconfirmed_reply_count
    ):
        return False
    transition.backfill_review_required = False
    transition.reviewed_at = datetime.now(UTC)
    db.commit()
    return True


def pending_work_counts(db: Session, mailbox: str) -> tuple[int, int]:
    """The same blocking work used by activation and the admin summary."""
    pending_tasks = TaskRepository(db).count_pending_for_mailbox(MailboxKey.of("imap", mailbox))
    captured_messages = db.query(ImapOutboxMessage.id).filter_by(
        mailbox=mailbox, status=ImapOutboxStatus.captured
    ).count()
    return pending_tasks, captured_messages


def has_pending_work(db: Session, mailbox: str) -> bool:
    return any(pending_work_counts(db, mailbox))


def transition_work(db: Session, transition: ImapAddressTransition) -> ImapTransitionWork:
    mailbox = transition.previous_mailbox
    pending_tasks, captured_messages = pending_work_counts(db, mailbox)
    # A completed transition is acknowledged through backfill-reviewed after the
    # admin has reviewed its warnings. Reply counts remain factual; only the
    # attention flag and action are cleared by the acknowledgement.
    reviewed = transition.status == "completed" and transition.reviewed_at is not None
    dead_letter_replies = db.query(IngestionTask.id).filter(
        IngestionTask.adapter == "imap",
        IngestionTask.mailbox == mailbox,
        IngestionTask.task_type == TaskType.send_message.value,
        IngestionTask.status == TaskStatus.dead_letter.value,
    ).count()
    unconfirmed_replies = db.query(ImapSentReply.idempotency_key).filter_by(
        mailbox=mailbox, status=ImapSentReplyStatus.sending
    ).count()
    waiting = transition.status == "waiting"
    actions = []
    if waiting:
        if transition.activation_error:
            actions.append("Correct the new IMAP connection and retry the address change, or cancel it.")
        elif pending_tasks or captured_messages:
            actions.append("Wait for old mailbox work to finish, then retry the address change.")
        else:
            actions.append("Retry the address change, or cancel it if the new address is no longer wanted.")
    if dead_letter_replies:
        actions.append(
            "Review old mailbox dead-letter replies in support monitoring and "
            "contact affected customers manually."
        )
    if unconfirmed_replies:
        actions.append(
            "Check unconfirmed sends in the old mailbox's Sent folder before "
            "contacting affected customers."
        )
    if transition.backfill_review_required:
        actions.append(
            "Review mail received in the new inbox before its first UID checkpoint; "
            "backdated messages may need a controlled manual backfill."
        )
    return ImapTransitionWork(
        previous_mailbox=mailbox,
        new_mailbox=transition.new_mailbox,
        status=transition.status,
        pending_task_count=pending_tasks,
        captured_message_count=captured_messages,
        dead_letter_reply_count=dead_letter_replies,
        unconfirmed_reply_count=unconfirmed_replies,
        backfill_review_required=transition.backfill_review_required,
        needs_attention=not reviewed and (
            waiting or dead_letter_replies > 0 or unconfirmed_replies > 0
            or transition.backfill_review_required
        ),
        action="" if reviewed else " ".join(actions) or None,
        activation_error=transition.activation_error,
    )


def address_owned_by_other_store(db: Session, mailbox: str, store_id: str) -> bool:
    return db.query(ImapAddressTransition.id).filter(
        ImapAddressTransition.store_id != store_id,
        ImapAddressTransition.status != "cancelled",
        or_(
            ImapAddressTransition.previous_mailbox == mailbox,
            ImapAddressTransition.new_mailbox == mailbox,
        ),
    ).first() is not None


def retired_mailboxes(db: Session, store_id: str) -> set[str]:
    return {
        mailbox for (mailbox,) in db.query(ImapAddressTransition.previous_mailbox).filter_by(
            store_id=store_id, status="completed"
        ).all()
    }


def captured_under_retired_address(
    db: Session, store_id: str, current_mailbox: str, external_message_id: str
) -> bool:
    """Avoid replaying a message the old address already handed to ingestion.

    Two addresses may resolve to the same physical IMAP inbox, as Gmail plus
    addresses do. The new cursor can intentionally overlap the old poller's work.
    """
    retired = select(ImapAddressTransition.previous_mailbox).where(
        ImapAddressTransition.store_id == store_id,
        ImapAddressTransition.status == "completed",
        ImapAddressTransition.previous_mailbox != current_mailbox,
    )
    return db.query(ImapOutboxMessage.id).filter(
        ImapOutboxMessage.mailbox.in_(retired),
        ImapOutboxMessage.external_message_id == external_message_id,
    ).first() is not None
