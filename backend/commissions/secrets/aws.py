"""AWS Secrets Manager backend (future).

Wire when SECRET_MANAGER_BACKEND=aws_secrets_manager. Credentials would be
stored as ARNs/names rather than Fernet blobs in the app database.
"""

from __future__ import annotations

from typing import Any

from .base import SecretManager


class AwsSecretsManager(SecretManager):
    def encrypt_credentials(self, credentials: dict[str, Any] | None) -> str:
        raise NotImplementedError(
            "AWS Secrets Manager backend is not enabled yet. "
            "Set SECRET_MANAGER_BACKEND=encrypted_db or implement aws.py."
        )

    def decrypt_credentials(
        self,
        blob: str | None,
        *,
        legacy_credentials: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "AWS Secrets Manager backend is not enabled yet. "
            "Set SECRET_MANAGER_BACKEND=encrypted_db or implement aws.py."
        )

    def rotate(self, blob: str | None, *, legacy_credentials: dict[str, Any] | None = None) -> str:
        raise NotImplementedError(
            "AWS Secrets Manager backend is not enabled yet."
        )
