import asyncio
import logging

from app.services.redis_service import RedisProvider

WAKEUP_KEY = "support:wakeup"

logger = logging.getLogger(__name__)


class SignalBus:
    def __init__(self, redis: RedisProvider) -> None:
        self._redis = redis

    async def signal_leader(self) -> None:
        try:
            await self._redis.async_.lpush(WAKEUP_KEY, "1")
        except Exception:
            logger.exception("signal_leader failed; relying on fallback poll")

    async def wait_for_signal(self, timeout: float) -> None:
        try:
            await self._redis.async_.blpop(WAKEUP_KEY, timeout=timeout)
        except Exception:
            logger.exception("BLPOP failed; falling back to sleep")
            await asyncio.sleep(timeout)

    async def clear(self) -> None:
        try:
            await self._redis.async_.delete(WAKEUP_KEY)
        except Exception:
            logger.exception("failed to clear wakeup key")


_signal_bus: SignalBus | None = None


def get_signal_bus() -> SignalBus:
    global _signal_bus
    if _signal_bus is None:
        _signal_bus = SignalBus(RedisProvider())
    return _signal_bus