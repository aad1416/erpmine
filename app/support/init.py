"""Support Email startup and shutdown, called from the app lifespan.

`start_support` discovers the Mailbox Adapters, builds the Mailbox Registry from their
Mailbox Connection tables, mounts their routes, starts them with the message sink and
starts the ingestion worker. `stop_support` stops the worker, then the adapters.

Mailbox Connections are read once here, so adding a Mailbox takes effect on the next
restart.

With the leadership pattern, only the leader runs adapters + ingestion. If a webhook hits a follower, the follower pushes a signal to Redis, and the leader picks it up! The leader also polls as a fallback, so a lost signal isn't fatal.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Mapping, Sequence

from fastapi import FastAPI

from app.config.setting import settings
from app.db.database import SessionLocal
from app.support.adapter.base import discover
from app.support.adapter.registry import MailboxRegistry
from app.support.ingestion.sink import message_sink
from app.support.ingestion.worker.ingestion_worker import IngestionWorker
from app.support.leader import SupportLeaderLock, try_acquire_support_leader
from app.support.signal_bus import get_signal_bus

logger = logging.getLogger(__name__)

_mailbox_registry: MailboxRegistry | None = None
_worker: IngestionWorker | None = None
_leader_lock: SupportLeaderLock | None = None
_is_leader: bool = False


def is_support_leader() -> bool:
    return _is_leader


async def start_support(app: FastAPI) -> MailboxRegistry:
    global _mailbox_registry, _worker, _leader_lock, _is_leader

    warn_if_multi_worker_without_flock()

    discover()
    db = SessionLocal()
    try:
        mailbox_registry = MailboxRegistry.load(db)
    finally:
        db.close()

    # Mount adapter HTTP routes on every process.
    app.include_router(mailbox_registry.router())
    _mailbox_registry = mailbox_registry

    lock = try_acquire_support_leader(settings.SUPPORT_LEADER_LOCK_FILE)
    if lock is None:
        _is_leader = False
        _leader_lock = None
        logger.info(
            "Support follower (pid=%s): skipping mailbox adapters and ingestion worker "
            "(another process holds %s)",
            os.getpid(),
            settings.SUPPORT_LEADER_LOCK_FILE,
        )
        return mailbox_registry

    _leader_lock = lock
    _is_leader = True
    await get_signal_bus().clear() 
    logger.info(
        "Support leader (pid=%s): starting mailbox adapters and ingestion worker",
        os.getpid(),
    )

    await mailbox_registry.start(message_sink)

    worker = IngestionWorker(
        mailbox_registry, settings.SUPPORT_WORKER_FALLBACK_INTERVAL_SECONDS,
        signal_bus=get_signal_bus()
    )
    worker.start()
    _worker = worker
    return mailbox_registry


async def stop_support() -> None:
    global _mailbox_registry, _worker, _leader_lock, _is_leader

    if _worker is not None:
        await _worker.stop()
        _worker = None

    if _is_leader and _mailbox_registry is not None:
        await _mailbox_registry.stop()

    _mailbox_registry = None

    if _leader_lock is not None:
        _leader_lock.release()
        _leader_lock = None

    _is_leader = False


def warn_if_multi_worker_without_flock(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None
) -> None:
    """
    Previously ``check_single_worker`` refused to boot. Leadership makes multi-worker
    safe on Unix; on platforms without flock we only warn.
    """
    try:
        import fcntl as _fcntl  # noqa: F401
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
