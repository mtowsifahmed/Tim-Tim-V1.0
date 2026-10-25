import pytest
from cryptography.fernet import Fernet
from app import crypto
from app.config import settings


def test_roundtrip_and_mask(monkeypatch):
    monkeypatch.setattr(settings, "key_encryption_secret", Fernet.generate_key().decode())
    c = crypto.encrypt("sk-secret-1234")
    assert "secret" not in c and crypto.decrypt(c) == "sk-secret-1234"
    assert crypto.mask(crypto.last4("sk-secret-1234")).endswith("1234")
    assert "sk-secret" not in crypto.mask("1234")


def test_whitespace_around_the_secret_is_ignored(monkeypatch):
    """A hand-edited .env can leave a stray space or CR; that must not break saving keys."""
    monkeypatch.setattr(settings, "key_encryption_secret", "  " + Fernet.generate_key().decode() + " \r")
    assert crypto.decrypt(crypto.encrypt("k")) == "k"


def test_broken_secret_says_what_to_do_instead_of_raising_a_bare_value_error(monkeypatch):
    """The bug that made Settings → API keys fail with an opaque 500: a 45-character secret (one stray character)."""
    good = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "key_encryption_secret", good[:20] + "A" + good[20:])
    with pytest.raises(crypto.KeySecretError) as e:
        crypto.encrypt("sk-secret-1234")
    assert "KEY_ENCRYPTION_SECRET" in str(e.value) and "Fernet.generate_key" in str(e.value)


def test_missing_secret_is_reported_clearly(monkeypatch):
    monkeypatch.setattr(settings, "key_encryption_secret", "")
    with pytest.raises(crypto.KeySecretError):
        crypto.encrypt("sk-secret-1234")
