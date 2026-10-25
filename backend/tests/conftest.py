import sys

import pytest


@pytest.fixture(autouse=True)
def _fresh_guard():
    """Each test starts with a clean flood-protection state (tests reuse one fake user)."""
    g = sys.modules.get("app.guard")
    if g:
        g._last.clear()
    yield


@pytest.fixture(autouse=True)
def _test_encryption_secret(monkeypatch):
    """Tests must not depend on a developer's private backend/.env: give them a throwaway encryption key."""
    from cryptography.fernet import Fernet
    from app.config import settings
    if not settings.key_encryption_secret.strip():
        monkeypatch.setattr(settings, "key_encryption_secret", Fernet.generate_key().decode())
    yield
