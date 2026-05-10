"""
Encryption service — variable-level wrapper around core encryption.

All variable read/write operations must go through this module.
Never access variable.value_encrypted directly from routes or other services.
"""

from __future__ import annotations

from app.core.encryption import encryption_service as _enc
from app.db.models import Variable


def encrypt_variable(value: str) -> str:
    """Encrypt a plaintext variable value for storage."""
    return _enc.encrypt(value)


def decrypt_variable(token: str) -> str:
    """Decrypt a stored variable token back to plaintext."""
    return _enc.decrypt(token)


def get_variable_value(variable: Variable, reveal_secret: bool = False) -> str:
    """
    Return the decrypted value of a variable.

    For secret variables, returns "***" unless reveal_secret is True.
    This is the only function routes should call when presenting variable values.
    """
    if variable.is_secret and not reveal_secret:
        return "***"
    return _enc.decrypt(variable.value_encrypted)
