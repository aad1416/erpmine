import redis
import redis.asyncio as redis_async
from app.config.setting import settings


class RedisService:
    def __init__(self, client: redis.Redis):
        self._client = client

    def get_token(self, token_id: str) -> str | None:
        value = self._client.get(token_id)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value


class RedisProvider:
    def __init__(self) -> None:
        self._sync: redis.Redis | None = None
        self._async: redis_async.Redis | None = None

    @property
    def sync(self) -> redis.Redis:
        if self._sync is None:
            self._sync = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=False,
            )
        return self._sync

    @property
    def async_(self) -> redis_async.Redis:
        if self._async is None:
            self._async = redis_async.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=False,
            )
        return self._async

    def service(self) -> RedisService:
        return RedisService(self.sync)

    async def close(self) -> None:
        if self._async is not None:
            await self._async.aclose()
            self._async = None
        if self._sync is not None:
            self._sync.close()
            self._sync = None