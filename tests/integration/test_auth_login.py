from app.api.dependencies import get_api_key_store, get_principal, get_user_store
from app.api.main import app
from app.core.security import create_access_token, hash_password

REGISTER = "/api/v1/rag/auth/register"
LOGIN = "/api/v1/rag/auth/login"
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


class _FakeApiKeyStore:
    def __init__(self, mapping=None):
        self._m = mapping or {}

    def get(self, raw_key):
        return self._m.get(raw_key)


def _unauth():
    # drop the conftest auto-auth so the real get_principal runs
    app.dependency_overrides.pop(get_principal, None)


async def test_register_returns_a_token_and_isolated_tenant(client):
    store = _FakeUserStore()
    app.dependency_overrides[get_user_store] = lambda: store

    resp = await client.post(
        REGISTER, json={"email": "Alice@example.com", "password": "s3cretpass"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert resp.json()["token_type"] == "bearer"

    user = store.get_by_email("alice@example.com")
    assert user["tenant_id"].startswith("t_")  # each signup gets its own tenant
    assert user["password_hash"] != "s3cretpass"  # hashed, never stored in clear


async def test_duplicate_email_is_409(client):
    store = _FakeUserStore()
    app.dependency_overrides[get_user_store] = lambda: store
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
    app.dependency_overrides[get_user_store] = lambda: store

    ok = await client.post(LOGIN, json={"email": "bob@example.com", "password": "rightpass1"})
    assert ok.status_code == 200 and ok.json()["access_token"]

    bad = await client.post(LOGIN, json={"email": "bob@example.com", "password": "nope"})
    assert bad.status_code == 401

    missing = await client.post(LOGIN, json={"email": "ghost@example.com", "password": "whatever1"})
    assert missing.status_code == 401


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


async def test_api_key_is_not_a_user_session(client):
    # an API key authenticates but has no user identity -> /me is 403
    _unauth()
    app.dependency_overrides[get_api_key_store] = lambda: _FakeApiKeyStore(
        {"sk_machine": {"tenant_id": "t-machine", "name": "ci"}}
    )
    resp = await client.get(ME, headers={"Authorization": "Bearer sk_machine"})
    assert resp.status_code == 403
