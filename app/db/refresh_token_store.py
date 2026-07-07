import secrets

from app.core.config import settings
from app.db.backend import make_kv


class RefreshTokenStore:
    """Server-side record of live refresh tokens, so sessions are revocable.

    Each refresh token has a random jti; `refresh:{jti}` -> user_id (with the
    token's TTL), and `user_refresh:{user_id}` indexes a user's jtis so all their
    sessions can be revoked at once (e.g. on a password/security change).
    """

    def __init__(self) -> None:
        self._redis = make_kv()
        self._ttl = settings.jwt_refresh_token_expire_days * 24 * 3600

    def _key(self, jti: str) -> str:
        return f"refresh:{jti}"

    def _user_index(self, user_id: str) -> str:
        return f"user_refresh:{user_id}"

    def issue(self, user_id: str) -> str:
        """Create and record a new jti; returns it."""
        jti = secrets.token_urlsafe(24)
        self._redis.set(self._key(jti), user_id, ex=self._ttl)
        self._redis.sadd(self._user_index(user_id), jti)
        return jti

    def is_valid(self, jti: str, user_id: str) -> bool:
        return self._redis.get(self._key(jti)) == user_id

    def revoke(self, jti: str, user_id: str) -> None:
        self._redis.delete(self._key(jti))
        self._redis.srem(self._user_index(user_id), jti)

    def revoke_all(self, user_id: str) -> int:
        jtis = self._redis.smembers(self._user_index(user_id))
        for jti in jtis:
            self._redis.delete(self._key(str(jti)))
        self._redis.delete(self._user_index(user_id))
        return len(jtis)
