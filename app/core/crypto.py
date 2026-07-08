"""At-rest encryption for local-mode state.

Server mode relies on infrastructure disk/volume encryption; local mode keeps
everything in files under ``data_dir``, so regulated / local-first users can turn
on application-managed encryption:

- the SQLite KV is encrypted **whole-database** by SQLCipher (``PRAGMA key``) —
  key NAMES (which can embed emails, e.g. ``user:email:...``) are covered, not
  just values (see ``app/db/backend.py``);
- sensitive Qdrant **chunk text** is encrypted per-field with Fernet
  (see ``app/db/qdrant_store.py``).

Enabled by configuring a key (``encryption_key`` directly, or
``encryption_key_file=True`` to load/generate one at ``data_dir/encryption.key``,
0600). No key -> no encryption (backward compatible). **Losing the key loses the
data — there is no recovery.**

Residual (documented, not covered): Qdrant structural metadata (titles/source
labels, tenant/collection/doc ids — the latter must stay queryable) and the
embedding vectors themselves. Keep metadata non-sensitive or rely on full-disk
encryption for it.
"""

import base64
import hashlib
import secrets
import threading

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Marker so decrypt can tell an encrypted field from legacy plaintext written
# before encryption was turned on (makes enabling migration-friendly for the
# vector store; the KV is whole-DB and needs no marker).
_ENC_PREFIX = "enc:v1:"

_fernet = None  # cached Fernet | None
_resolved_key: str | None = None
_lock = threading.Lock()


def _load_or_generate_key_file() -> str:
    """Return the key stored at data_dir/encryption.key, creating it (0600) once."""
    path = settings.encryption_key_path
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    # Create with 0600 from the start — never briefly world-readable.
    import os

    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(key)
    logger.info("encryption_key_generated", path=str(path))
    return key


def encryption_key() -> str | None:
    """The effective at-rest key, or None when encryption is off."""
    global _resolved_key
    if _resolved_key is not None:
        return _resolved_key
    with _lock:
        if _resolved_key is not None:
            return _resolved_key
        # Only local mode encrypts at the app layer; server deployments use
        # Redis + external Qdrant and rely on infrastructure disk encryption.
        if settings.app_mode != "local":
            return None
        if settings.encryption_key:
            _resolved_key = settings.encryption_key
        elif settings.encryption_key_file:
            _resolved_key = _load_or_generate_key_file()
        return _resolved_key


def is_enabled() -> bool:
    return encryption_key() is not None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    # Resolve the key BEFORE taking _lock — encryption_key() locks internally,
    # and _lock is not reentrant (nesting would deadlock).
    key = encryption_key()
    if key is None:
        return None
    with _lock:
        if _fernet is not None:
            return _fernet
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:  # pragma: no cover - guarded by the extra
            raise RuntimeError(
                "encryption is enabled but 'cryptography' is missing — install the "
                "'encryption' extra (pip install -e '.[encryption]')"
            ) from exc
        # Fernet needs 32 url-safe-base64 bytes; derive deterministically from the
        # configured passphrase/key. Fernet supplies its own IV + auth tag.
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        _fernet = Fernet(derived)
        return _fernet


def encrypt_field(value: str) -> str:
    """Encrypt a string for storage; pass through unchanged when disabled."""
    fernet = _get_fernet()
    if fernet is None or value == "":
        return value
    token = fernet.encrypt(value.encode()).decode()
    return _ENC_PREFIX + token


def decrypt_field(value: str) -> str:
    """Decrypt a value written by ``encrypt_field``; legacy plaintext passes through."""
    if not value.startswith(_ENC_PREFIX):
        return value  # written before encryption was enabled, or encryption off
    fernet = _get_fernet()
    if fernet is None:
        # Encrypted data but no key configured — cannot recover; surface it.
        raise RuntimeError("encrypted field found but no encryption key is configured")
    from cryptography.fernet import InvalidToken

    try:
        return fernet.decrypt(value[len(_ENC_PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("failed to decrypt field — wrong encryption key?") from exc


def reset_for_tests() -> None:
    """Drop cached key/cipher so tests can repoint settings."""
    global _fernet, _resolved_key
    with _lock:
        _fernet = None
        _resolved_key = None
