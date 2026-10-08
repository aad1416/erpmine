"""Support Email startup and shutdown, called from the app lifespan.

`start_support` discovers the Mailbox Adapters, builds the Mailbox Registry from their
Mailbox Connection tables, mounts their routes, starts them with the message sink and
starts the ingestion worker. `stop_support` stops the worker, then the adapters.

Mailbox Connections are read once here, so adding a Mailbox takes effect on the next
restart.
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

logger = logging.getLogger(__name__)

_mailbox_registry: MailboxRegistry | None = None
_worker: IngestionWorker | None = None


async def start_support(app: FastAPI) -> MailboxRegistry:
    global _mailbox_registry, _worker
    check_single_worker()
    discover()
    db = SessionLocal()
    try:
        mailbox_registry = MailboxRegistry.load(db)
    finally:
        db.close()
    app.include_router(mailbox_registry.router())
    await mailbox_registry.start(message_sink)
    _mailbox_registry = mailbox_registry

    worker = IngestionWorker(
        mailbox_registry, settings.SUPPORT_WORKER_FALLBACK_INTERVAL_SECONDS
    )
    worker.start()
    _worker = worker
    return mailbox_registry


async def stop_support() -> None:
    """The worker first, so no reply is sent through an adapter being stopped."""
    global _mailbox_registry, _worker
    if _worker is not None:
        await _worker.stop()
        _worker = None
    if _mailbox_registry is not None:
        await _mailbox_registry.stop()
        _mailbox_registry = None


def check_single_worker(
    argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None
) -> None:
    """Refuses more than one uvicorn worker process: each would start every adapter and
    poll the same Mailboxes. Checks what uvicorn itself reads, since every worker process
    inherits it: `--workers N` / `--workers=N` on the command line, else the
    `WEB_CONCURRENCY` environment variable. `--reload` makes uvicorn ignore both. Other
    process managers (e.g. gunicorn `-w`) are not detected."""
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    if "--reload" in argv:
        return
    workers = _workers_option(argv)
    source = "--workers"
    if workers is None and environ.get("WEB_CONCURRENCY"):
        workers = environ["WEB_CONCURRENCY"]
        source = "WEB_CONCURRENCY"
    if workers is None:
        return
    try:
        worker_count = int(workers)
    except ValueError:
        raise RuntimeError(f"{source} is not a number: {workers!r}") from None
    if worker_count > 1:
        raise RuntimeError(
            f"Support Email needs a single uvicorn worker, but {source} is {worker_count}: "
            "each worker would start every Mailbox Adapter and poll the same Mailboxes. "
            "Run it with one worker."
        )


def _workers_option(argv: Sequence[str]) -> str | None:
    for index, argument in enumerate(argv):
        if argument == "--workers" and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--workers="):
            return argument.partition("=")[2]
    return None
