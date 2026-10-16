from fastapi import Request
from app.services.redis_service import RedisService


def get_redis_service(request: Request) -> RedisService:
    return request.app.state.redis.service()