"""Tests for the credential encryption helpers (app.core.security, issue #45)."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core import security
from app.core.config import get_settings
from app.core.security import CredentialCipher


def test_encrypt_decrypt_round_trips() -> None:
    cipher = CredentialCipher(Fernet.generate_key())
    secret = "ya29.a-real-looking-oauth-access-token"

    token = cipher.encrypt(secret)

    assert token != secret
    assert secret not in token  # plaintext must not be embedded in the ciphertext
    assert cipher.decrypt(token) == secret


def test_encryption_is_non_deterministic_but_decrypts_the_same() -> None:
    cipher = CredentialCipher(Fernet.generate_key())
    secret = "s3-secret-access-key"

    first = cipher.encrypt(secret)
    second = cipher.encrypt(secret)

    # Fernet embeds a fresh timestamp + IV each call, so identical input yields distinct tokens.
    assert first != second
    assert cipher.decrypt(first) == cipher.decrypt(second) == secret


def test_decrypt_with_a_different_key_raises() -> None:
    writer = CredentialCipher(Fernet.generate_key())
    attacker = CredentialCipher(Fernet.generate_key())
    token = writer.encrypt("refresh-token")

    with pytest.raises(InvalidToken):
        attacker.decrypt(token)


def test_get_credential_cipher_uses_the_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    base = get_settings()
    monkeypatch.setattr(
        security, "get_settings", lambda: base.model_copy(update={"encryption_key": key})
    )
    security.get_credential_cipher.cache_clear()
    try:
        cipher = security.get_credential_cipher()
        assert cipher.decrypt(cipher.encrypt("hello")) == "hello"
    finally:
        security.get_credential_cipher.cache_clear()


def test_get_credential_cipher_raises_a_clear_error_when_key_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = get_settings()
    monkeypatch.setattr(
        security, "get_settings", lambda: base.model_copy(update={"encryption_key": ""})
    )
    security.get_credential_cipher.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
            security.get_credential_cipher()
    finally:
        security.get_credential_cipher.cache_clear()
