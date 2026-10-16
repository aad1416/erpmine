from app.services.redis_service import RedisService, create_redis_client


def get_redis_service() -> RedisService:
    """Dependency injection for RedisService."""
    return RedisService(create_redis_client())
