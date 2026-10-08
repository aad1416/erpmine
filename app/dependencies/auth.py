from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.models.Users import User
from app.services.redis_service import RedisService
from app.dependencies.redis import get_redis_service
from app.utils.auth import decode_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    redis_service: RedisService = Depends(get_redis_service),
) -> User:
    """Dependency to get the current user from a Redis-backed JWT token."""
    token_id = credentials.credentials
    token = redis_service.get_token(token_id)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str | None = payload.get("id")
    username: str | None = payload.get("username")
    if user_id is None or username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing required user claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    first_name: str = payload.get("firstName", "")
    last_name: str = payload.get("lastName", "")
    store_id: str = payload.get("storeId", "")
    roles = payload.get("roles", [])
    accesses: list = payload.get("accesses", [])
    admin_roles = {"Manager Full Access", "Store Owner"}
    user_type = "admin" if any(r in admin_roles for r in roles) else "user"

    user = User(
        id=user_id,
        name=f"{first_name} {last_name}".strip(),
        username=username,
        password="",
        user_type=user_type,
        store_id=store_id,
        accesses=accesses,
    )
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to check if the current user is an admin."""
    if current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have admin privileges",
        )
    return current_user
