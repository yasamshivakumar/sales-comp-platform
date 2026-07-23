"""Secret Manager abstraction for Incentra credential storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SecretManager(ABC):
    """Provider-agnostic interface for sealing CRM credentials.

    Current production backend: EncryptedDatabaseSecretManager (Fernet blob
    stored on ExternalIntegration.encrypted_credentials).

    Future backends (AWS Secrets Manager, Azure Key Vault, Hashicorp Vault)
    implement the same interface without changing call sites.
    """

    @abstractmethod
    def encrypt_credentials(self, credentials: dict[str, Any] | None) -> str:
        """Return an opaque sealed blob suitable for database storage."""

    @abstractmethod
    def decrypt_credentials(
        self,
        blob: str | None,
        *,
        legacy_credentials: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return plaintext credentials dict for connector use."""

    @abstractmethod
    def rotate(self, blob: str | None, *, legacy_credentials: dict[str, Any] | None = None) -> str:
        """Re-seal credentials under the current encryption key."""

    def delete(self, secret_id: str) -> None:
        """Optional remote secret deletion (no-op for encrypted_db)."""
        return None
