"""At-rest field encryption (crypto.encrypt_field / decrypt_field) + key file."""

import os
import stat

import pytest

from app.core import crypto


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # Each test controls the key; drop the cached cipher/key before and after.
    crypto.reset_for_tests()
    monkeypatch.setattr(crypto.settings, "app_mode", "local")
    monkeypatch.setattr(crypto.settings, "encryption_key", None)
    monkeypatch.setattr(crypto.settings, "encryption_key_file", False)
    yield
    crypto.reset_for_tests()


def test_disabled_is_passthrough(monkeypatch):
    assert not crypto.is_enabled()
    assert crypto.encrypt_field("hello") == "hello"
    assert crypto.decrypt_field("hello") == "hello"


def test_roundtrip_when_enabled(monkeypatch):
    monkeypatch.setattr(crypto.settings, "encryption_key", "s3cret-pass")
    crypto.reset_for_tests()

    token = crypto.encrypt_field("patient record: John Doe")
    assert token != "patient record: John Doe"
    assert "John Doe" not in token  # ciphertext, not obfuscation
    assert token.startswith("enc:v1:")
    assert crypto.decrypt_field(token) == "patient record: John Doe"


def test_empty_string_is_not_encrypted(monkeypatch):
    monkeypatch.setattr(crypto.settings, "encryption_key", "k")
    crypto.reset_for_tests()
    assert crypto.encrypt_field("") == ""


def test_decrypt_legacy_plaintext_passes_through(monkeypatch):
    # Data written before encryption was enabled has no marker prefix.
    monkeypatch.setattr(crypto.settings, "encryption_key", "k")
    crypto.reset_for_tests()
    assert crypto.decrypt_field("old plaintext value") == "old plaintext value"


def test_wrong_key_fails_loudly(monkeypatch):
    monkeypatch.setattr(crypto.settings, "encryption_key", "right-key")
    crypto.reset_for_tests()
    token = crypto.encrypt_field("data")

    monkeypatch.setattr(crypto.settings, "encryption_key", "wrong-key")
    crypto.reset_for_tests()
    with pytest.raises(RuntimeError, match="wrong encryption key"):
        crypto.decrypt_field(token)


def test_encrypted_field_without_key_raises(monkeypatch):
    monkeypatch.setattr(crypto.settings, "encryption_key", "k")
    crypto.reset_for_tests()
    token = crypto.encrypt_field("data")

    monkeypatch.setattr(crypto.settings, "encryption_key", None)
    crypto.reset_for_tests()
    with pytest.raises(RuntimeError, match="no encryption key"):
        crypto.decrypt_field(token)


def test_key_file_generated_0600(monkeypatch, tmp_path):
    monkeypatch.setattr(crypto.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(crypto.settings, "encryption_key_file", True)
    crypto.reset_for_tests()

    key1 = crypto.encryption_key()
    assert key1
    key_path = tmp_path / "encryption.key"
    assert key_path.exists()
    assert stat.S_IMODE(os.stat(key_path).st_mode) == 0o600

    # Second resolution reuses the same persisted key (stable across restarts).
    crypto.reset_for_tests()
    assert crypto.encryption_key() == key1
