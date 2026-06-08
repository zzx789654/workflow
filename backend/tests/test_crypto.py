"""Unit tests for app.core.crypto (no DB needed)."""

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_decrypt_roundtrip():
    plain = "super-secret-password"
    enc = encrypt_secret(plain)
    assert enc != plain
    assert decrypt_secret(enc) == plain


def test_encrypt_empty_returns_empty():
    assert encrypt_secret("") == ""


def test_decrypt_empty_returns_empty():
    assert decrypt_secret("") == ""


def test_decrypt_invalid_returns_empty():
    assert decrypt_secret("not-a-valid-token") == ""


def test_mask_secret():
    assert mask_secret("anything") == "••••••••"
    assert mask_secret("") == ""
