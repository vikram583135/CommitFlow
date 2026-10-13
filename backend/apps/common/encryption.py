"""
Field-level symmetric encryption service using Fernet.
Ensures zero plaintext API keys or OAuth tokens in database columns or logs.
"""

import base64
from cryptography.fernet import Fernet
from django.conf import settings

def _get_fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

def encrypt_secret(plaintext: str) -> str:
    """Encrypt a string and return a base64-encoded encrypted string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    encrypted_bytes = f.encrypt(plaintext.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')

def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a base64-encoded encrypted string back to plaintext."""
    if not ciphertext:
        return ""
    f = _get_fernet()
    decrypted_bytes = f.decrypt(ciphertext.encode('utf-8'))
    return decrypted_bytes.decode('utf-8')

def mask_secret(secret: str, visible_suffix_len: int = 4) -> str:
    """
    Return a masked representation for UI display, e.g. '••••••••abcd'.
    Never displays the full secret.
    """
    if not secret:
        return ""
    if len(secret) <= visible_suffix_len:
        return "•" * len(secret)
    return "•" * 8 + secret[-visible_suffix_len:]
