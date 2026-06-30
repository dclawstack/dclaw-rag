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


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return the claims for a valid access token, else None (bad signature,
    expired, malformed, or wrong type)."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return claims if claims.get("type") == "access" else None
