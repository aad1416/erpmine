"""Drains PendingLogSync with retry-and-backoff (02-architecture-decisions.md §8) —
without this job the queue communication_log_client.enqueue_backfill() writes to would
never be read. Same AsyncIOScheduler + fcntl-lock pattern as
app/services/seed_scheduler.py.

Lives under app/services/ (flat, AI-core side), not app/support/ingestion/worker/ —
despite reusing the same scheduler pattern as the ingestion jobs, this one operates
purely on AI-core tables (PendingLogSync, ConversationMessage) via
communication_log_client.py, which the isolation boundary (§9.1) keeps out of
app/support/ entirely.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config.setting import settings
from app.db.database import SessionLocal
from app.db.models.ConversationMessage import ConversationMessage
from app.db.models.PendingLogSync import PendingLogSync
from app.services.communication_log_client import CommunicationLogClient
from app.services.seed_scheduler import seed_file_lock

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# Generous backoff ceiling before giving up on a single pending sync row — separate
# from the ingestion task queue's 3-retry cap, since this is a lower-stakes background
# sync rather than a customer-facing action.
_MAX_ATTEMPTS = 5


async def run_log_sync_retry_job() -> None:
    with seed_file_lock(f"{settings.SUPPORT_LOCK_FILE}.log_sync_retry") as acquired:
        if not acquired:
            logger.info("Log sync retry skipped — another worker holds the lock")
            return
        await _drain_pending()


async def _drain_pending() -> None:
    client = CommunicationLogClient()
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        pending_rows = (
            db.query(PendingLogSync)
            .filter(
                PendingLogSync.status == "pending",
                PendingLogSync.next_attempt_at <= now,
            )
            .order_by(PendingLogSync.created_at.asc())
            .all()
        )
        for row in pending_rows:
            message = db.get(ConversationMessage, row.conversation_message_id)
            if message is None:
                row.status = "dead_letter"
                db.commit()
                continue

            success = await client.send_message(row.ticket_id, message.body_text)
            row.attempt_count += 1
            if success:
                row.status = "done"
                message.synced_to_ticket_log = True
            elif row.attempt_count >= _MAX_ATTEMPTS:
                row.status = "dead_letter"
            else:
                backoff_seconds = min(60 * (2**row.attempt_count), 3600)
                row.next_attempt_at = now + timedelta(seconds=backoff_seconds)
            db.commit()
    finally:
        db.close()


def start_log_sync_retry_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_log_sync_retry_job,
        "interval",
        seconds=settings.SUPPORT_LOG_SYNC_RETRY_INTERVAL_SECONDS,
        id="support_log_sync_retry",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(
        "Log sync retry scheduler started (interval=%ss)",
        settings.SUPPORT_LOG_SYNC_RETRY_INTERVAL_SECONDS,
    )


def stop_log_sync_retry_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Log sync retry scheduler stopped")
