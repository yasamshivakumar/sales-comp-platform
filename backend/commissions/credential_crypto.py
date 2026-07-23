"""Encrypt CRM credentials at rest (Fernet).

Writes always require cryptography + a configured key.
Legacy unprefixed plaintext remains readable until re-encrypt migrates rows.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("commissions")

SECRET_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "password",
        "client_secret",
        "api_key",
        "security_token",
    }
)

_PREFIX = "enc:v1:"
_MASK = "••••••••"


class CredentialEncryptionError(Exception):
    """Raised when credentials cannot be sealed or unsealed safely."""


def _key_material(raw: str) -> bytes:
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet_for_material(raw: str):
    from cryptography.fernet import Fernet

    return Fernet(_key_material(raw))


def encryption_key_candidates() -> list[str]:
    """Current key first, then previous keys for rotation decrypt."""
    keys: list[str] = []
    current = (getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None) or "").strip()
    if current:
        keys.append(current)
    for previous in getattr(settings, "CREDENTIALS_ENCRYPTION_PREVIOUS_KEYS", None) or []:
        previous = str(previous).strip()
        if previous and previous not in keys:
            keys.append(previous)
    # Local/dev fallback only when DEBUG and no dedicated key configured.
    if not keys and getattr(settings, "DEBUG", False):
        secret = (getattr(settings, "SECRET_KEY", None) or "").strip()
        if secret:
            keys.append(secret)
    return keys


def require_cryptography():
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except ImportError as exc:
        raise ImproperlyConfigured(
            "The 'cryptography' package is required for CRM credential encryption. "
            "Install it via backend/requirements.txt."
        ) from exc


def require_encryption_key(*, for_write: bool = False) -> str:
    candidates = encryption_key_candidates()
    if not candidates:
        raise ImproperlyConfigured(
            "CREDENTIALS_ENCRYPTION_KEY is required to encrypt CRM credentials. "
            "Set it in the environment (see backend/.env.example)."
        )
    return candidates[0]


def validate_encryption_ready(*, strict: bool | None = None) -> None:
    """Refuse unsafe startup configurations.

    When strict (default: not DEBUG), cryptography and CREDENTIALS_ENCRYPTION_KEY
    are mandatory. In DEBUG, cryptography is still required so local writes seal.
    """
    if strict is None:
        strict = not bool(getattr(settings, "DEBUG", True))

    require_cryptography()

    if strict:
        key = (getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None) or "").strip()
        if not key:
            raise ImproperlyConfigured(
                "CREDENTIALS_ENCRYPTION_KEY is required when DEBUG=False."
            )
        # Prove the key material is usable.
        _fernet_for_material(key)


def _fernets_for_decrypt():
    require_cryptography()
    from cryptography.fernet import Fernet

    materials = encryption_key_candidates()
    if not materials:
        raise CredentialEncryptionError("No credential encryption keys configured")
    return [Fernet(_key_material(raw)) for raw in materials]


def _fernet_for_encrypt():
    require_cryptography()
    key = require_encryption_key(for_write=True)
    return _fernet_for_material(key)


def encrypt_value(value: str) -> str:
    if value is None:
        return value
    text = str(value)
    if not text or text.startswith(_PREFIX):
        return text
    token = _fernet_for_encrypt().encrypt(text.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_value(value: str) -> str:
    if not value or not str(value).startswith(_PREFIX):
        return value
    token = str(value)[len(_PREFIX) :].encode("ascii")
    last_error: Exception | None = None
    for fernet in _fernets_for_decrypt():
        try:
            return fernet.decrypt(token).decode("utf-8")
        except Exception as exc:  # noqa: BLE001 — try next rotation key
            last_error = exc
            continue
    raise CredentialEncryptionError(
        "Unable to decrypt credential value with configured keys"
    ) from last_error


def public_credential_metadata(credentials: dict | None) -> dict:
    """Non-secret fields safe to keep in the JSON credentials column."""
    data = {}
    for key, value in (credentials or {}).items():
        if key in SECRET_KEYS:
            continue
        data[key] = value
    return data


def seal_credentials(credentials: dict | None) -> dict:
    """Return a copy with secret string values Fernet-encrypted (field-level)."""
    data = dict(credentials or {})
    for key in list(data.keys()):
        if key in SECRET_KEYS and isinstance(data[key], str) and data[key]:
            if data[key] == _MASK:
                continue
            data[key] = encrypt_value(data[key])
    return data


def unseal_credentials(credentials: dict | None) -> dict:
    data = dict(credentials or {})
    for key in list(data.keys()):
        if isinstance(data[key], str) and data[key].startswith(_PREFIX):
            data[key] = decrypt_value(data[key])
        elif key in SECRET_KEYS and isinstance(data[key], str) and data[key] and not data[key].startswith(_PREFIX):
            logger.warning(
                "Legacy plaintext CRM secret detected for key=%s; run reencrypt_integration_credentials",
                key,
            )
    return data


def mask_credentials(credentials: dict | None) -> dict:
    data = {}
    for key, value in (credentials or {}).items():
        if key in SECRET_KEYS:
            data[key] = _MASK if value else ""
        else:
            data[key] = value
    return data


def redact_secrets(payload: Any) -> Any:
    """Recursively redact secret keys for audit logs / API error detail."""
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if key in SECRET_KEYS or key in {
                "credentials",
                "encrypted_credentials",
                "password",
                "token",
                "access_token",
                "refresh_token",
                "client_secret",
                "api_key",
                "security_token",
            }:
                out[key] = _MASK if value else value
            else:
                out[key] = redact_secrets(value)
        return out
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    return payload


def credentials_blob_encrypt(credentials: dict | None) -> str:
    """Seal secrets then encrypt the full JSON blob. Always requires Fernet."""
    sealed = seal_credentials(credentials)
    raw = json.dumps(sealed, separators=(",", ":"), sort_keys=True)
    return encrypt_value(raw)


def credentials_blob_decrypt(blob: str | None, fallback: dict | None = None) -> dict:
    if not blob:
        if fallback:
            logger.warning(
                "CRM credentials loaded from legacy JSON column; run reencrypt_integration_credentials"
            )
        return unseal_credentials(fallback)
    if blob.startswith(_PREFIX):
        try:
            raw = decrypt_value(blob)
            return unseal_credentials(json.loads(raw))
        except CredentialEncryptionError:
            raise
        except Exception as exc:
            if fallback:
                logger.warning(
                    "Encrypted credentials blob decrypt failed (%s); trying legacy JSON",
                    exc,
                )
                return unseal_credentials(fallback)
            raise CredentialEncryptionError("Invalid encrypted credentials blob") from exc
    # Legacy: blob stored as raw JSON string without enc:v1 prefix.
    logger.warning(
        "CRM credentials blob is unencrypted JSON; run reencrypt_integration_credentials"
    )
    try:
        return unseal_credentials(json.loads(blob))
    except Exception:
        return unseal_credentials(fallback)
