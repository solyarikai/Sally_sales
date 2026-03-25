"""Simple encryption for stored API keys using Fernet (AES)."""
import os
import base64
import hashlib
from cryptography.fernet import Fernet


def _get_key() -> bytes:
    """Get or derive encryption key."""
    raw = os.getenv("ENCRYPTION_KEY", "mcp-default-encryption-key-change-in-prod")
    # Derive a valid Fernet key from whatever string is provided
    digest = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_get_key())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt an encrypted string value."""
    return _fernet.decrypt(ciphertext.encode()).decode()
