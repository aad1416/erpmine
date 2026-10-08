from fastapi import HTTPException
from typing import Optional

from app.config.setting import settings
from app.repositories.lyndom_db import LyndomDBRepository


def get_lyndom_db() -> LyndomDBRepository:
    if not settings.lyndom_db_url:
        raise HTTPException(status_code=503, detail="Lyndom database is not configured")
    return LyndomDBRepository(settings.lyndom_db_url)


def get_lyndom_db_optional() -> Optional[LyndomDBRepository]:
    """Returns Lyndom repository when configured; otherwise None (no HTTP error)."""
    if not settings.lyndom_db_url:
        return None
    return LyndomDBRepository(settings.lyndom_db_url)
