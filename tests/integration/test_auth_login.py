from app.api.dependencies import (
    get_api_key_store,
    get_principal,
    get_rate_limiter,
    get_refresh_token_store,
    get_user_store,
)
from app.api.main import app
from app.core.security import create_access_token, hash_password

REGISTER = "/api/v1/rag/auth/register"
LOGIN = "/api/v1/rag/auth/login"
REFRESH = "/api/v1/rag/auth/refresh"
LOGOUT = "/api/v1/rag/auth/logout"
ME = "/api/v1/rag/auth/me"


class _FakeUserStore:
    def __init__(self):
        self.by_email = {}
        self.by_id = {}

    def create(self, record):
        if record["email"] in self.by_email:
            raise ValueError("email already registered")
        self.by_email[record["email"]] = record
        self.by_id[record["id"]] = record
        return record

    def get_by_email(self, email):
        return self.by_email.get(email.lower())

    def get_by_id(self, user_id):
        return self.by_id.get(user_id)


class _FakeRefreshStore:
    def __init__(self):
        self._live = {}
        self._n = 0

    def issue(self, user_id):
        self._n += 1
        jti = f"jti{self._n}"
        self._live[jti] = user_id
        return jti

    def is_valid(self, jti, user_id):
        return self._live.get(jti) == user_id

    def revoke(self, jti, user_id):
        self._live.pop(jti, None)

    def revoke_all(self, user_id):
        n = sum(1 for u in self._live.values() if u == user_id)
        self._live = {j: u for j, u in self._live.items() if u != user_id}
        return n


class _FakeApiKeyStore:
    def __init__(self, mapping=None):
        self._m = mapping or {}

    def get(self, raw_key):
        return self._m.get(raw_key)


def _use_stores(users=None, refresh=None):
    users = users or _FakeUserStore()
    refresh = refresh or _FakeRefreshStore()
    app.dependency_overrides[get_user_store] = lambda: users
    app.dependency_overrides[get_refresh_token_store] = lambda: refresh


def _unauth():
    app.dependency_overrides.pop(get_principal, None)


async def test_register_returns_tokens_and_isolated_tenant(client):
    store = _FakeUserStore()
    _use_stores(users=store)

    resp = await client.post(
        REGISTER, json={"email": "Alice@example.com", "password": "s3cretpass"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"

    user = store.get_by_email("alice@example.com")
    assert user["tenant_id"].startswith("t_")
    assert user["password_hash"] != "s3cretpass"


async def test_duplicate_email_is_409(client):
    store = _FakeUserStore()
    _use_stores(users=store)
    await client.post(REGISTER, json={"email": "dup@example.com", "password": "s3cretpass"})
    again = await client.post(REGISTER, json={"email": "dup@example.com", "password": "other123"})
    assert again.status_code == 409


async def test_login_succeeds_and_rejects_bad_password(client):
    store = _FakeUserStore()
    store.by_email["bob@example.com"] = store.by_id["u-bob"] = {
        "id": "u-bob",
        "email": "bob@example.com",
        "password_hash": hash_password("rightpass1"),
        "tenant_id": "t_bob",
    }
    _use_stores(users=store)

    ok = await client.post(LOGIN, json={"email": "bob@example.com", "password": "rightpass1"})
    assert ok.status_code == 200 and ok.json()["access_token"] and ok.json()["refresh_token"]

    bad = await client.post(LOGIN, json={"email": "bob@example.com", "password": "nope"})
    assert bad.status_code == 401

    missing = await client.post(LOGIN, json={"email": "ghost@example.com", "password": "whatever1"})
    assert missing.status_code == 401


async def test_refresh_rotates_and_revokes_old(client):
    store = _FakeUserStore()
    store.by_email["c@d.com"] = store.by_id["u-c"] = {
        "id": "u-c",
        "email": "c@d.com",
        "password_hash": hash_password("rightpass1"),
        "tenant_id": "t_c",
    }
    _use_stores(users=store)

    tokens = (await client.post(LOGIN, json={"email": "c@d.com", "password": "rightpass1"})).json()
    old_refresh = tokens["refresh_token"]

    rotated = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != old_refresh  # rotated

    # the old refresh token is now revoked
    reused = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert reused.status_code == 401


async def test_logout_revokes_refresh(client):
    store = _FakeUserStore()
    store.by_email["e@f.com"] = store.by_id["u-e"] = {
        "id": "u-e",
        "email": "e@f.com",
        "password_hash": hash_password("rightpass1"),
        "tenant_id": "t_e",
    }
    _use_stores(users=store)

    refresh_token = (
        await client.post(LOGIN, json={"email": "e@f.com", "password": "rightpass1"})
    ).json()["refresh_token"]

    assert (await client.post(LOGOUT, json={"refresh_token": refresh_token})).status_code == 200
    # cannot refresh after logout
    assert (await client.post(REFRESH, json={"refresh_token": refresh_token})).status_code == 401


async def test_refresh_rejects_garbage(client):
    _use_stores()
    assert (await client.post(REFRESH, json={"refresh_token": "not.a.jwt"})).status_code == 401


async def test_me_with_jwt_returns_identity(client):
    _unauth()
    app.dependency_overrides[get_api_key_store] = lambda: _FakeApiKeyStore()
    token = create_access_token(user_id="u-7", tenant_id="t-7", email="c@d.com")

    resp = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"id": "u-7", "email": "c@d.com", "tenant_id": "t-7"}


async def test_me_requires_auth(client):
    _unauth()
    app.dependency_overrides[get_api_key_store] = lambda: _FakeApiKeyStore()
    assert (await client.get(ME)).status_code == 401


async def test_register_is_ip_rate_limited(client):
    _use_stores()
    app.dependency_overrides[get_rate_limiter] = lambda: _BlockingLimiter()
    resp = await client.post(REGISTER, json={"email": "x@example.com", "password": "s3cretpass"})
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "30"


class _BlockingLimiter:
    def check(self, key, limit=None):
        return False, 30


async def test_api_key_is_not_a_user_session(client):
    _unauth()
    app.dependency_overrides[get_api_key_store] = lambda: _FakeApiKeyStore(
        {"sk_machine": {"tenant_id": "t-machine", "name": "ci"}}
    )
    resp = await client.get(ME, headers={"Authorization": "Bearer sk_machine"})
    assert resp.status_code == 403
