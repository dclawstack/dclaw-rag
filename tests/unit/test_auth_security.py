from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"  # not stored in clear
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_verify_handles_garbage_hash():
    assert verify_password("x", "not-a-real-argon2-hash") is False


def test_token_roundtrip_carries_claims():
    token = create_access_token(user_id="u1", tenant_id="t1", email="a@b.com")
    claims = decode_access_token(token)
    assert claims is not None
    assert claims["sub"] == "u1"
    assert claims["tenant_id"] == "t1"
    assert claims["email"] == "a@b.com"
    assert claims["type"] == "access"


def test_tampered_token_is_rejected():
    token = create_access_token(user_id="u1", tenant_id="t1", email="a@b.com")
    assert decode_access_token(token + "x") is None
    assert decode_access_token("not.a.jwt") is None


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "jwt_access_token_expire_minutes", -1)
    token = create_access_token(user_id="u1", tenant_id="t1", email="a@b.com")
    assert decode_access_token(token) is None


def test_token_signed_with_other_secret_is_rejected(monkeypatch):
    token = create_access_token(user_id="u1", tenant_id="t1", email="a@b.com")
    monkeypatch.setattr(settings, "jwt_secret", "a-different-secret-entirely-xxxxxx")
    assert decode_access_token(token) is None


def test_access_and_refresh_types_are_not_interchangeable():
    access = create_access_token(user_id="u1", tenant_id="t1", email="a@b.com")
    refresh = create_refresh_token(user_id="u1", tenant_id="t1", email="a@b.com", jti="j1")

    # each decoder only accepts its own token type
    assert decode_access_token(access) is not None
    assert decode_refresh_token(access) is None
    assert decode_refresh_token(refresh) is not None
    assert decode_access_token(refresh) is None
    assert decode_refresh_token(refresh)["jti"] == "j1"
