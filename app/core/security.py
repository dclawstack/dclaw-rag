"""Password hashing (argon2) and JWT access tokens for end-user auth."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import settings

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, ValueError):
        return False


def create_access_token(*, user_id: str, tenant_id: str, email: str) -> str:
    now = datetime.now(tz=UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def create_refresh_token(*, user_id: str, tenant_id: str, email: str, jti: str) -> str:
    now = datetime.now(tz=UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def _decode(token: str, expected_type: str) -> dict[str, Any] | None:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return claims if claims.get("type") == expected_type else None


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Claims for a valid access token, else None (bad/expired/wrong-type)."""
    return _decode(token, "access")


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """Claims for a valid refresh token, else None."""
    return _decode(token, "refresh")
