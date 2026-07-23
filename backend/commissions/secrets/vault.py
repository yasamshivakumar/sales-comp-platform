"""Hashicorp Vault backend (future).

Wire when SECRET_MANAGER_BACKEND=hashicorp_vault.
"""

from __future__ import annotations

from typing import Any

from .base import SecretManager


class HashicorpVaultSecretManager(SecretManager):
    def encrypt_credentials(self, credentials: dict[str, Any] | None) -> str:
        raise NotImplementedError(
            "Hashicorp Vault backend is not enabled yet. "
            "Set SECRET_MANAGER_BACKEND=encrypted_db or implement vault.py."
        )

    def decrypt_credentials(
        self,
        blob: str | None,
        *,
        legacy_credentials: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Hashicorp Vault backend is not enabled yet. "
            "Set SECRET_MANAGER_BACKEND=encrypted_db or implement vault.py."
        )

    def rotate(self, blob: str | None, *, legacy_credentials: dict[str, Any] | None = None) -> str:
        raise NotImplementedError(
            "Hashicorp Vault backend is not enabled yet."
        )
