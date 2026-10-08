import redis
from app.config.setting import settings


class RedisService:
    def __init__(self, client: redis.Redis):
        self._client = client

    def get_token(self, token_id: str) -> str | None:
        """Retrieve the JWT token stored under the given token_id key."""
        value = self._client.get(token_id)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value


def create_redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        decode_responses=False,
    )
