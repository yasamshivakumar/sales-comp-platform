"""Secret manager backends for CRM credentials and future vault integrations."""

from __future__ import annotations

from django.conf import settings

from .base import SecretManager
from .encrypted_db import EncryptedDatabaseSecretManager


def get_secret_manager() -> SecretManager:
    backend = (getattr(settings, "SECRET_MANAGER_BACKEND", None) or "encrypted_db").strip().lower()
    if backend in {"encrypted_db", "database", "db", ""}:
        return EncryptedDatabaseSecretManager()
    if backend in {"aws", "aws_secrets_manager"}:
        from .aws import AwsSecretsManager

        return AwsSecretsManager()
    if backend in {"azure", "azure_key_vault"}:
        from .azure import AzureKeyVaultSecretManager

        return AzureKeyVaultSecretManager()
    if backend in {"vault", "hashicorp", "hashicorp_vault"}:
        from .vault import HashicorpVaultSecretManager

        return HashicorpVaultSecretManager()
    raise ValueError(f"Unknown SECRET_MANAGER_BACKEND: {backend!r}")
