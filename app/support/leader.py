"""Process-lifetime leader lock for Support background work.

On platforms without fcntl, every process becomes leader so local
dev still works; production Support is expected to run on Linux.
"""

from __future__ import annotations

import logging
import os
from types import TracebackType

try:
    import fcntl
except ImportError:  # non-unix
    fcntl = None

logger = logging.getLogger(__name__)


class SupportLeaderLock:
    """Holds an exclusive non-blocking file lock until `release`."""

    def __init__(self, lock_path: str, lock_file: object) -> None:
        self.lock_path = lock_path
        self._lock_file = lock_file
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if fcntl is not None:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                logger.exception("Failed to unlock support leader lock %s", self.lock_path)
        try:
            self._lock_file.close()
        except OSError:
            logger.exception("Failed to close support leader lock file %s", self.lock_path)

    def __enter__(self) -> "SupportLeaderLock":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def try_acquire_support_leader(lock_path: str) -> SupportLeaderLock | None:
    """Try to become the Support leader for this process."""
    if fcntl is None:
        logger.warning(
            "fcntl unavailable — this process assumes Support leadership "
            "(multi-process Support requires a Unix flock)"
        )
        lock_dir = os.path.dirname(lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
        lock_file = open(lock_path, "a+")
        return SupportLeaderLock(lock_path, lock_file)

    lock_dir = os.path.dirname(lock_path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    lock_file = open(lock_path, "a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    except Exception:
        lock_file.close()
        raise

    # record the holder for operators inspecting the lock file.
    try:
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(f"pid={os.getpid()}\n")
        lock_file.flush()
    except OSError:
        logger.exception("Could not write pid to support leader lock %s", lock_path)

    return SupportLeaderLock(lock_path, lock_file)
