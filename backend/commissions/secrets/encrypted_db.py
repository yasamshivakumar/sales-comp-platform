"""Fernet-encrypted credentials stored in the application database."""

from __future__ import annotations

from typing import Any

from .. import credential_crypto as crypto
from .base import SecretManager


class EncryptedDatabaseSecretManager(SecretManager):
    """Seal secrets with Fernet and store the blob on the integration row."""

    def encrypt_credentials(self, credentials: dict[str, Any] | None) -> str:
        crypto.validate_encryption_ready(strict=False)
        return crypto.credentials_blob_encrypt(credentials or {})

    def decrypt_credentials(
        self,
        blob: str | None,
        *,
        legacy_credentials: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return crypto.credentials_blob_decrypt(blob, fallback=legacy_credentials)

    def rotate(self, blob: str | None, *, legacy_credentials: dict[str, Any] | None = None) -> str:
        plaintext = self.decrypt_credentials(blob, legacy_credentials=legacy_credentials)
        return self.encrypt_credentials(plaintext)
