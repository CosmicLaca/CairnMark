"""Recoverable encryption for provider API tokens."""

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config import PROJECT_ROOT

SECRET_DIR = PROJECT_ROOT / ".secret"
KEY_FILE = SECRET_DIR / "encryption.key"


def _ensure_key():
    """Return the Fernet key, creating it on first use."""
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    SECRET_DIR.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    KEY_FILE.chmod(0o600)
    return key


def encrypt_token(plaintext):
    """Encrypt a token for storage. Returns None for empty input."""
    if not plaintext:
        return None
    key = _ensure_key()
    return Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_token(ciphertext):
    """Decrypt a stored token. Returns None when missing or invalid."""
    if not ciphertext:
        return None
    if not KEY_FILE.exists():
        # No encryption key yet: treat stored value as a legacy plain token.
        return ciphertext
    try:
        key = KEY_FILE.read_bytes().strip()
        return Fernet(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, OSError):
        # Fall back to treating the stored value as a legacy plain token
        # so existing setups keep working until they are re-saved.
        return ciphertext