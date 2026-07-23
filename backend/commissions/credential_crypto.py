"""Encrypt CRM credentials at rest (Fernet). Legacy plaintext remains readable."""

from __future__ import annotations

import base64
import hashlib
import json

from django.conf import settings


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


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    raw = (getattr(settings, "CREDENTIALS_ENCRYPTION_KEY", None) or settings.SECRET_KEY or "").encode(
        "utf-8"
    )
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_value(value: str) -> str:
    if not value or str(value).startswith(_PREFIX):
        return value
    f = _fernet()
    if f is None:
        return value
    token = f.encrypt(str(value).encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_value(value: str) -> str:
    if not value or not str(value).startswith(_PREFIX):
        return value
    f = _fernet()
    if f is None:
        return value
    token = str(value)[len(_PREFIX) :].encode("ascii")
    try:
        return f.decrypt(token).decode("utf-8")
    except Exception:
        return value


def seal_credentials(credentials: dict | None) -> dict:
    data = dict(credentials or {})
    for key in list(data.keys()):
        if key in SECRET_KEYS and isinstance(data[key], str) and data[key]:
            if data[key] == "••••••••":
                continue
            data[key] = encrypt_value(data[key])
    return data


def unseal_credentials(credentials: dict | None) -> dict:
    data = dict(credentials or {})
    for key in list(data.keys()):
        if isinstance(data[key], str) and data[key].startswith(_PREFIX):
            data[key] = decrypt_value(data[key])
    return data


def mask_credentials(credentials: dict | None) -> dict:
    data = {}
    for key, value in (credentials or {}).items():
        if key in SECRET_KEYS:
            data[key] = "••••••••" if value else ""
        else:
            data[key] = value
    return data


def credentials_blob_encrypt(credentials: dict | None) -> str:
    sealed = seal_credentials(credentials)
    raw = json.dumps(sealed, separators=(",", ":"))
    return encrypt_value(raw) if _fernet() else raw


def credentials_blob_decrypt(blob: str | None, fallback: dict | None = None) -> dict:
    if not blob:
        return unseal_credentials(fallback)
    if blob.startswith(_PREFIX):
        try:
            raw = decrypt_value(blob)
            return unseal_credentials(json.loads(raw))
        except Exception:
            return unseal_credentials(fallback)
    try:
        return unseal_credentials(json.loads(blob))
    except Exception:
        return unseal_credentials(fallback)
