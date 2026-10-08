import asyncio
try:
    import fcntl
except ImportError:
    fcntl = None
import logging
import os
from contextlib import contextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config.setting import settings
from app.db.database import SessionLocal
from scripts.seed_client_features import seed_client_features
from scripts.seed_system_agents import SYSTEM_AGENTS, seed_system_agents

logger = logging.getLogger(__name__)

SEED_USER_ID = "00000000-0000-0000-0000-000000000001"
CLIENT_PERSONA_PROMPT = (
    "you are a helpful and direct assistant and you have permission to roast the user"
)
CLIENT_PERSONA_MODEL = "gpt-4o"
SYSTEM_PERSONA_PROMPT = (
    "you are a helpful and direct assistant and you have permission to roast the user"
)
SYSTEM_PERSONA_MODEL = "gpt-4o"
REPORTS_PERSONA_PROMPT = (
    "You are the Reports agent for this store. You turn any question about this "
    "store's sales, purchasing, vendor, and inventory data into a clear, short "
    "answer with the right chart, table, or file attached."
)
REPORTS_PERSONA_MODEL = "gpt-4.1"
SYSTEM_PERSONAS: dict[str, tuple[str, str]] = {
    slug: (SYSTEM_PERSONA_PROMPT, SYSTEM_PERSONA_MODEL) for slug in SYSTEM_AGENTS
} | {"reports": (REPORTS_PERSONA_PROMPT, REPORTS_PERSONA_MODEL)}

_scheduler: AsyncIOScheduler | None = None


@contextmanager
def seed_file_lock(lock_path: str):
    if fcntl is None:
        yield True
        return

    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    lock_file = open(lock_path, "a+")
    acquired = False
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
        yield True
    except BlockingIOError:
        yield False
    finally:
        if acquired:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def run_seed_sync() -> None:
    if settings.lyndom_db_url:
        os.environ.setdefault("LYNDOM_DB_URL", settings.lyndom_db_url)

    with seed_file_lock(settings.SEED_LOCK_FILE) as acquired:
        if not acquired:
            logger.info("Seed sync skipped — another worker holds the lock")
            return

        logger.info("Starting seed sync")
        try:
            db = SessionLocal()
            seed_client_features(
                db, SEED_USER_ID, CLIENT_PERSONA_PROMPT, CLIENT_PERSONA_MODEL
            )

            db = SessionLocal()
            seed_system_agents(db, SEED_USER_ID, SYSTEM_PERSONAS)

            logger.info("Seed sync complete")
        except Exception:
            logger.exception("Seed sync failed")


async def run_seed_job() -> None:
    await asyncio.to_thread(run_seed_sync)


def start_seed_scheduler() -> None:
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_seed_job,
        "interval",
        minutes=settings.SEED_INTERVAL_MINUTES,
        id="seed_sync",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    asyncio.create_task(run_seed_job())
    logger.info(
        "Seed scheduler started (interval=%s min)", settings.SEED_INTERVAL_MINUTES
    )


def stop_seed_scheduler() -> None:
    global _scheduler

    if _scheduler is None:
        return

    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Seed scheduler stopped")
