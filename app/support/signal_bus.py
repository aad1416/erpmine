import asyncio
import logging

from app.services.redis_service import RedisProvider

WAKEUP_KEY = "support:wakeup"
ADAPTER_NOTICE_KEY = "support:adapter_notice"

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

    async def signal_adapter_notice(self, address: str) -> None:
        try:
            await self._redis.async_.lpush(ADAPTER_NOTICE_KEY, address)
        except Exception:
            logger.exception("signal_adapter_notice failed; relying on adapter backup poll")

    async def wait_for_adapter_notice(self, timeout: float) -> str | None:
        try:
            result = await self._redis.async_.blpop(ADAPTER_NOTICE_KEY, timeout=timeout)
        except Exception:
            logger.exception("adapter-notice BLPOP failed; falling back to sleep")
            await asyncio.sleep(timeout)
            return None
        if not result:
            return None
        _key, value = result
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    async def clear(self) -> None:
        try:
            await self._redis.async_.delete(WAKEUP_KEY, ADAPTER_NOTICE_KEY)
        except Exception:
            logger.exception("failed to clear wakeup keys")


_signal_bus: SignalBus | None = None


def init_signal_bus(redis: RedisProvider) -> SignalBus:
    global _signal_bus
    _signal_bus = SignalBus(redis)
    return _signal_bus


def get_signal_bus() -> SignalBus:
    if _signal_bus is None:
        raise RuntimeError(
            "SignalBus not initialised — call init_signal_bus(app.state.redis) "
            "from the lifespan before using Support"
        )
    return _signal_bus