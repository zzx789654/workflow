"""Fernet-based symmetric encryption for secret settings (LDAP/RADIUS credentials)."""

import base64
import os

from cryptography.fernet import Fernet, InvalidToken

# Key loaded once at import time from environment.
# If not set, generate a runtime-only key (secrets are not persisted securely between restarts).
_raw_key = os.environ.get("SETTINGS_ENCRYPT_KEY", "")
if _raw_key:
    # Validate and normalise: accept raw 32-byte hex or 44-char base64url
    try:
        if len(_raw_key) == 64:  # hex
            _fernet_key = base64.urlsafe_b64encode(bytes.fromhex(_raw_key))
        else:
            _fernet_key = _raw_key.encode()
        _fernet = Fernet(_fernet_key)
    except Exception:
        _fernet_key = Fernet.generate_key()
        _fernet = Fernet(_fernet_key)
else:
    _fernet_key = Fernet.generate_key()
    _fernet = Fernet(_fernet_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string; returns base64url ciphertext."""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt ciphertext produced by encrypt_secret; returns plaintext."""
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        return ""


MASK = "••••••••"


def mask_secret(value: str) -> str:
    return MASK if value else ""
