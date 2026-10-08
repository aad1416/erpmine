from typing import Optional
from jose import JWTError, jwt
from app.config.setting import settings


def decode_access_token(token: str) -> Optional[dict]:
    """Decode a JWT access token without verifying signature or expiry."""
    try:
        payload = jwt.decode(
            token,
            settings.access_token_secret_key,
            algorithms=[settings.access_token_algorithm],
            options={
                "verify_signature": False,
                "verify_exp": False,
            },
        )
        return payload
    except JWTError:
        return None
