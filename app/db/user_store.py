import json

import redis

from app.core.config import settings


class UserStore:
    """End-user accounts in Redis. Each user belongs to exactly one tenant.

    Records: {id, email, password_hash, tenant_id, created_at}. Email is the
    unique login handle, indexed via a SETNX so registration is race-safe.
    """

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    def _key(self, user_id: str) -> str:
        return f"user:{user_id}"

    def _email_key(self, email: str) -> str:
        return f"user:email:{email.lower()}"

    def create(self, record: dict) -> dict:
        """Persist a new user. Raises ValueError if the email is already taken."""
        if not self._redis.setnx(self._email_key(record["email"]), record["id"]):
            raise ValueError("email already registered")
        self._redis.set(self._key(record["id"]), json.dumps(record))
        return record

    def get_by_id(self, user_id: str) -> dict | None:
        raw = self._redis.get(self._key(user_id))
        return json.loads(raw) if raw else None

    def get_by_email(self, email: str) -> dict | None:
        user_id = self._redis.get(self._email_key(email))
        return self.get_by_id(str(user_id)) if user_id else None
