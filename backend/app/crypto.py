from cryptography.fernet import Fernet

from .config import settings

HELP = ('KEY_ENCRYPTION_SECRET in backend/.env must be the 44-character key printed by\n'
        '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
        'Generate a new one and restart the backend.')


class KeySecretError(RuntimeError):
    """KEY_ENCRYPTION_SECRET is missing or malformed, so saved keys can neither be stored nor read."""


def _f() -> Fernet:
    secret = settings.key_encryption_secret.strip()
    if not secret:
        raise KeySecretError("KEY_ENCRYPTION_SECRET is not set in backend/.env.\n" + HELP)
    try:
        return Fernet(secret.encode())
    except (ValueError, TypeError) as e:          # wrong length, not base64, stray characters
        raise KeySecretError("The KEY_ENCRYPTION_SECRET in backend/.env is not a valid key.\n" + HELP) from e


def encrypt(plain: str) -> str:
    return _f().encrypt(plain.encode()).decode()


def decrypt(cipher: str) -> str:
    return _f().decrypt(cipher.encode()).decode()


def last4(plain: str) -> str:
    return plain[-4:]


def mask(l4: str) -> str:
    return "•" * 8 + l4
