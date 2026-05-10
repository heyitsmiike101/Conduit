"""
Encryption layer for Conduit.

Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) from the
cryptography library. The secret key is generated on first run and stored
at data/.secret_key with mode 600 (owner read/write only).

Never store the raw key anywhere other than that file.
Never pass decrypted secrets to logs.
"""

import logging
import stat
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


class EncryptionService:
    """
    Manages the platform encryption key and provides encrypt/decrypt operations.

    The key file is created on first instantiation. On subsequent runs the
    existing key is loaded. If the key file is corrupted or unreadable an
    EncryptionError is raised immediately so the problem surfaces at startup.
    """

    def __init__(self, key_path: Optional[Path] = None) -> None:
        self._key_path = key_path or settings.secret_key_path
        self._fernet = self._load_or_create_key()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_or_create_key(self) -> Fernet:
        """Load existing key or generate and persist a new one."""
        if self._key_path.exists():
            return self._load_key()
        return self._generate_key()

    def _generate_key(self) -> Fernet:
        """Generate a new Fernet key, write it to disk with mode 600."""
        self._key_path.parent.mkdir(parents=True, exist_ok=True)

        key = Fernet.generate_key()

        # Write the key file
        self._key_path.write_bytes(key)

        # Restrict to owner read/write only (chmod 600)
        self._key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)

        logger.info("Generated new encryption key at %s", self._key_path)
        return Fernet(key)

    def _load_key(self) -> Fernet:
        """Load the existing key from disk."""
        try:
            key = self._key_path.read_bytes().strip()
            fernet = Fernet(key)
            logger.debug("Loaded encryption key from %s", self._key_path)
            return fernet
        except (ValueError, TypeError) as exc:
            raise EncryptionError(
                f"Encryption key at {self._key_path} is invalid or corrupted. "
                "Delete the file to generate a fresh key (WARNING: this will "
                "make all existing encrypted values unreadable)."
            ) from exc

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def encrypt(self, value: str) -> str:
        """
        Encrypt a plaintext string.

        Returns a URL-safe base64-encoded token. Fernet encryption is
        non-deterministic — encrypting the same value twice produces
        different tokens, both of which decrypt correctly.

        Args:
            value: The plaintext string to encrypt.

        Returns:
            An encrypted token string.
        """
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str) -> str:
        """
        Decrypt a token produced by encrypt().

        Args:
            token: The encrypted token string.

        Returns:
            The original plaintext string.

        Raises:
            EncryptionError: If the token is invalid, tampered with, or was
                encrypted with a different key.
        """
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise EncryptionError(
                "Failed to decrypt token. The token may be invalid, tampered "
                "with, or was encrypted with a different key."
            ) from exc


# Exported singleton — import this everywhere
encryption_service = EncryptionService()
