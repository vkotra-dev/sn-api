from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from app.core.config import get_settings

settings = get_settings()


def create_access_token(*, subject: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_exp_minutes)
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"verify_aud": False},
    )


def is_valid_token_payload(payload: dict[str, Any]) -> bool:
    return all(key in payload for key in ("sub", "email", "role", "exp"))
