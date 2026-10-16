"""Support Email startup and shutdown, called from the app lifespan.

`start_support` discovers the Mailbox Adapters, builds the Mailbox Registry from their
Mailbox Connection tables, mounts their routes, starts them with the message sink and
starts the ingestion worker. `stop_support` stops the worker, then the adapters.

IMAP Mailbox settings can also be activated in the running adapter after a save.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Mapping, Sequence

from fastapi import FastAPI

from app.config.setting import settings
from app.db.database import SessionLocal
from app.services.redis_service import RedisProvider
from app.support.adapter.base import discover
from app.support.adapter.registry import MailboxRegistry
from app.support.ingestion.sink import message_sink
from app.support.ingestion.worker.ingestion_worker import IngestionWorker
from app.support.leader import (
    SupportLeaderLock,
    is_support_leader,
    set_support_leader,
    try_acquire_support_leader,
)
from app.support.signal_bus import get_signal_bus, init_signal_bus

logger = logging.getLogger(__name__)

__all__ = ["start_support", "stop_support", "is_support_leader", "check_single_worker"]

_mailbox_registry: MailboxRegistry | None = None
_worker: IngestionWorker | None = None
_leader_lock: SupportLeaderLock | None = None


def _ensure_signal_bus(app: FastAPI) -> None:
    redis = getattr(app.state, "redis", None)
    if not isinstance(redis, RedisProvider):
        redis = RedisProvider()
        app.state.redis = redis
    init_signal_bus(redis)


async def start_support(app: FastAPI) -> MailboxRegistry:
    global _mailbox_registry, _leader_lock

    warn_if_multi_worker_without_flock()
    _ensure_signal_bus(app)

    discover()
    db = SessionLocal()
    try:
        mailbox_registry = MailboxRegistry.load(db)
    finally:
        db.close()

    app.include_router(mailbox_registry.router())
    _mailbox_registry = mailbox_registry
    app.state.support_mailbox_registry = mailbox_registry

    lock = try_acquire_support_leader(settings.SUPPORT_LEADER_LOCK_FILE)
    if lock is None:
        set_support_leader(False)
        logger.info(
            "Support follower (pid=%s): skipping mailbox adapters and ingestion worker "
            "(another process holds %s)",
            os.getpid(),
            settings.SUPPORT_LEADER_LOCK_FILE,
        )
        return mailbox_registry

    set_support_leader(True)
    try:
        await get_signal_bus().clear()
        logger.info(
            "Support leader (pid=%s): starting mailbox adapters and ingestion worker",
            os.getpid(),
        )
        await mailbox_registry.start(message_sink)
        await _start_ingestion_worker(mailbox_registry)
    except Exception:
        logger.exception("Support leader startup failed; releasing the lock")
        await _roll_back_leader(mailbox_registry)
        lock.release()
        raise

    _leader_lock = lock
    return mailbox_registry


async def _start_ingestion_worker(mailbox_registry: MailboxRegistry) -> None:
    global _worker
    worker = IngestionWorker(
        mailbox_registry,
        settings.SUPPORT_WORKER_FALLBACK_INTERVAL_SECONDS,
        signal_bus=get_signal_bus(),
    )
    _worker = worker
    try:
        worker.start()
    except Exception:
        _worker = None
        await worker.stop()
        raise


async def _roll_back_leader(mailbox_registry: MailboxRegistry) -> None:
    global _worker
    set_support_leader(False)
    if _worker is not None:
        await _worker.stop()
        _worker = None
    try:
        await mailbox_registry.stop()
    except Exception:
        logger.exception("Failed to stop mailbox adapters after a leader startup error")


async def stop_support() -> None:
    global _mailbox_registry, _worker, _leader_lock

    if _worker is not None:
        await _worker.stop()
        _worker = None

    if is_support_leader() and _mailbox_registry is not None:
        await _mailbox_registry.stop()

    _mailbox_registry = None

    if _leader_lock is not None:
        _leader_lock.release()
        _leader_lock = None

    set_support_leader(False)


def warn_if_multi_worker_without_flock(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None
) -> None:
    try:
        import fcntl as _fcntl
    except ImportError:
        count = _configured_worker_count(argv, environ)
        if count is not None and count > 1:
            logger.warning(
                "WEB_CONCURRENCY/--workers is %s but fcntl is unavailable: every "
                "process will run Support adapters and the ingestion worker. "
                "Use a single worker or run Support on Linux.",
                count,
            )


def check_single_worker(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None
) -> None:
    warn_if_multi_worker_without_flock(argv, environ)


def _configured_worker_count(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None
) -> int | None:
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    if "--reload" in argv:
        return 1
    workers = _workers_option(argv)
    if workers is None and environ.get("WEB_CONCURRENCY"):
        workers = environ["WEB_CONCURRENCY"]
    if workers is None:
        return None
    try:
        return int(workers)
    except ValueError:
        return None


def _workers_option(argv: Sequence[str]) -> str | None:
    for index, argument in enumerate(argv):
        if argument == "--workers" and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--workers="):
            return argument.partition("=")[2]
    return None