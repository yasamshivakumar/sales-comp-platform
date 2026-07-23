"""Phase 1.3 authentication hardening services.

Password history/expiry, MFA (TOTP), trusted devices, login events,
suspicious IP detection, and auth session tracking.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("commissions")

MFA_PENDING_TTL_SECONDS = 300
MFA_PENDING_PREFIX = "mfa-pending:"


def org_policy(organization):
    """Return effective security policy with safe defaults."""

    class _Policy:
        require_mfa = False
        password_history_count = 5
        password_max_age_days = 0
        session_idle_minutes = 0
        max_concurrent_sessions = 1
        remember_device_days = 30
        alert_on_new_login_ip = True

    if organization is None:
        return _Policy()
    return organization


def effective_token_ttl_minutes(organization=None):
    org_minutes = int(getattr(organization, "session_idle_minutes", 0) or 0)
    if org_minutes > 0:
        return org_minutes
    return int(getattr(settings, "TOKEN_TTL_MINUTES", 60) or 60)


def _hash_token_key(token_key: str) -> str:
    return hashlib.sha256(token_key.encode("utf-8")).hexdigest()


def record_login_event(
    *,
    organization=None,
    user=None,
    email="",
    outcome="",
    ip_address=None,
    user_agent="",
    device_id="",
    suspicious=False,
    suspicion_reason="",
    detail=None,
):
    from .models import LoginEvent

    try:
        return LoginEvent.objects.create(
            organization=organization,
            user=user,
            email=(email or getattr(user, "email", "") or "")[:254],
            outcome=outcome,
            ip_address=ip_address or None,
            user_agent=(user_agent or "")[:300],
            device_id=(device_id or "")[:64],
            suspicious=bool(suspicious),
            suspicion_reason=(suspicion_reason or "")[:255],
            detail=detail or {},
        )
    except Exception:
        logger.exception("Failed to write LoginEvent")
        return None


def password_in_history(user, raw_password: str) -> bool:
    from .models import PasswordHistory

    org = None
    from .tenants import get_profile_for_user

    profile = get_profile_for_user(user)
    if profile:
        org = profile.organization
    count = int(getattr(org_policy(org), "password_history_count", 5) or 0)
    if count <= 0:
        return False
    # Also reject reuse of the current password.
    if user.has_usable_password() and check_password(raw_password, user.password):
        return True
    for row in PasswordHistory.objects.filter(user=user).order_by("-created_at")[:count]:
        if check_password(raw_password, row.password_hash):
            return True
    return False


def apply_password_update(user, raw_password: str, *, organization=None):
    """Set a new password, append previous hash to history, clear force-change."""
    from .models import PasswordHistory, UserProfile
    from .tenants import get_profile_for_user

    previous_hash = user.password
    user.set_password(raw_password)
    user.save(update_fields=["password"])
    if previous_hash:
        PasswordHistory.objects.create(user=user, password_hash=previous_hash)
        org = organization
        profile = get_profile_for_user(user, organization=organization)
        if profile and not org:
            org = profile.organization
        keep = int(getattr(org_policy(org), "password_history_count", 5) or 5)
        keep = max(keep, 1)
        ids = list(
            PasswordHistory.objects.filter(user=user)
            .order_by("-created_at")
            .values_list("id", flat=True)[keep:]
        )
        if ids:
            PasswordHistory.objects.filter(id__in=ids).delete()

    now = timezone.now()
    profile = get_profile_for_user(user, organization=organization)
    if profile:
        profile.password_changed_at = now
        profile.force_password_change = False
        profile.save(update_fields=["password_changed_at", "force_password_change"])
    else:
        UserProfile.objects.filter(email__iexact=user.email).update(
            password_changed_at=now, force_password_change=False
        )


def record_password_change(user, *, organization=None):
    """Backward-compatible alias — prefer apply_password_update for new code."""
    # No-op if called after set_password without previous hash capture.
    from .models import UserProfile
    from .tenants import get_profile_for_user

    now = timezone.now()
    profile = get_profile_for_user(user, organization=organization)
    if profile:
        profile.password_changed_at = now
        profile.force_password_change = False
        profile.save(update_fields=["password_changed_at", "force_password_change"])
    else:
        UserProfile.objects.filter(email__iexact=user.email).update(
            password_changed_at=now, force_password_change=False
        )


def password_is_expired(user, organization=None) -> bool:
    from .tenants import get_profile_for_user

    profile = get_profile_for_user(user, organization=organization)
    org = organization or (profile.organization if profile else None)
    max_age = int(getattr(org_policy(org), "password_max_age_days", 0) or 0)
    if max_age <= 0:
        return bool(profile and profile.force_password_change)
    if profile and profile.force_password_change:
        return True
    changed = getattr(profile, "password_changed_at", None) if profile else None
    if not changed:
        # Never changed tracked — treat as expired when policy enabled.
        return True
    return changed < timezone.now() - timedelta(days=max_age)


def is_device_trusted(user, device_id: str, organization=None) -> bool:
    from .models import TrustedDevice

    device_id = (device_id or "").strip()
    if not device_id:
        return False
    now = timezone.now()
    return TrustedDevice.objects.filter(
        user=user,
        device_id=device_id,
        revoked_at__isnull=True,
        trusted_until__gte=now,
    ).exists()


def remember_device(user, device_id: str, *, organization=None, ip=None, user_agent="", device_name=""):
    from .models import TrustedDevice

    device_id = (device_id or "").strip()
    if not device_id:
        device_id = uuid.uuid4().hex
    days = int(getattr(org_policy(organization), "remember_device_days", 30) or 30)
    until = timezone.now() + timedelta(days=max(days, 1))
    obj, _ = TrustedDevice.objects.update_or_create(
        user=user,
        device_id=device_id,
        defaults={
            "organization": organization,
            "device_name": (device_name or "Browser")[:120],
            "user_agent": (user_agent or "")[:300],
            "last_ip": ip,
            "trusted_until": until,
            "revoked_at": None,
        },
    )
    return obj


def revoke_trusted_device(user, device_id: str):
    from .models import TrustedDevice

    TrustedDevice.objects.filter(user=user, device_id=device_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def user_has_confirmed_mfa(user) -> bool:
    from .models import UserMfaDevice

    return UserMfaDevice.objects.filter(
        user=user, is_active=True, confirmed_at__isnull=False
    ).exists()


def mfa_required_for_login(user, organization, device_id: str) -> bool:
    if is_device_trusted(user, device_id, organization=organization):
        return False
    org_requires = bool(getattr(org_policy(organization), "require_mfa", False))
    if org_requires or user_has_confirmed_mfa(user):
        # Org requires MFA even if user has not enrolled yet → still challenge
        # only when they have a confirmed device; otherwise force enroll later.
        return user_has_confirmed_mfa(user)
    return False


def _encrypt_mfa_secret(secret: str) -> str:
    from .credential_crypto import encrypt_value

    return encrypt_value(secret)


def _decrypt_mfa_secret(blob: str) -> str:
    from .credential_crypto import decrypt_value

    return decrypt_value(blob)


def start_totp_enrollment(user, *, name="Authenticator"):
    """Create an unconfirmed TOTP device and return provisioning details."""
    import pyotp

    from .models import UserMfaDevice

    secret = pyotp.random_base32()
    device = UserMfaDevice.objects.create(
        user=user,
        name=(name or "Authenticator")[:100],
        secret_encrypted=_encrypt_mfa_secret(secret),
        confirmed_at=None,
        is_active=True,
    )
    totp = pyotp.TOTP(secret)
    issuer = getattr(settings, "MFA_TOTP_ISSUER", "Incentra")
    uri = totp.provisioning_uri(name=user.email or user.username, issuer_name=issuer)
    return device, secret, uri


def confirm_totp_enrollment(user, device_id: int, code: str) -> bool:
    import pyotp

    from .models import UserMfaDevice, UserProfile

    device = UserMfaDevice.objects.filter(user=user, pk=device_id, is_active=True).first()
    if not device:
        return False
    secret = _decrypt_mfa_secret(device.secret_encrypted)
    if not pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1):
        return False
    device.confirmed_at = timezone.now()
    device.last_used_at = timezone.now()
    device.save(update_fields=["confirmed_at", "last_used_at"])
    UserProfile.objects.filter(email__iexact=user.email).update(mfa_enabled=True)
    # Remove other unconfirmed devices for cleanliness
    UserMfaDevice.objects.filter(user=user, confirmed_at__isnull=True).exclude(pk=device.pk).delete()
    return True


def verify_totp_code(user, code: str) -> bool:
    import pyotp

    from .models import UserMfaDevice

    for device in UserMfaDevice.objects.filter(
        user=user, is_active=True, confirmed_at__isnull=False
    ):
        secret = _decrypt_mfa_secret(device.secret_encrypted)
        if pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1):
            device.last_used_at = timezone.now()
            device.save(update_fields=["last_used_at"])
            return True
    return False


def create_mfa_pending_token(user, *, ip="", user_agent="", device_id="", remember=False) -> str:
    token = secrets.token_urlsafe(32)
    cache.set(
        f"{MFA_PENDING_PREFIX}{token}",
        {
            "user_id": user.pk,
            "ip": ip,
            "user_agent": user_agent,
            "device_id": device_id,
            "remember": bool(remember),
        },
        MFA_PENDING_TTL_SECONDS,
    )
    return token


def consume_mfa_pending_token(mfa_token: str):
    key = f"{MFA_PENDING_PREFIX}{mfa_token}"
    payload = cache.get(key)
    if not payload:
        return None
    cache.delete(key)
    return payload


def evaluate_suspicious_login(user, ip_address, organization=None) -> tuple[bool, str]:
    from .models import LoginEvent

    if not ip_address:
        return False, ""
    if not bool(getattr(org_policy(organization), "alert_on_new_login_ip", True)):
        return False, ""
    seen = LoginEvent.objects.filter(
        user=user,
        outcome=LoginEvent.OUTCOME_SUCCESS,
        ip_address=ip_address,
    ).exists()
    if seen:
        return False, ""
    prior = LoginEvent.objects.filter(user=user, outcome=LoginEvent.OUTCOME_SUCCESS).exists()
    if not prior:
        return False, ""
    return True, "new_ip_address"


def create_auth_session(user, token_key, *, organization=None, ip=None, user_agent="", device_id=""):
    from .models import UserAuthSession

    # Enforce single active API token: mark older sessions revoked.
    UserAuthSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now(),
        revoke_reason="replaced",
    )
    return UserAuthSession.objects.create(
        user=user,
        organization=organization,
        session_key=uuid.uuid4().hex,
        token_key_hash=_hash_token_key(token_key),
        ip_address=ip,
        user_agent=(user_agent or "")[:300],
        device_id=(device_id or "")[:64],
    )


def revoke_auth_sessions_for_user(user, *, reason="logout"):
    from .models import UserAuthSession
    from rest_framework.authtoken.models import Token

    UserAuthSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now(),
        revoke_reason=reason,
    )
    Token.objects.filter(user=user).delete()


def touch_auth_session_for_token(user, token_key):
    from .models import UserAuthSession

    if not token_key:
        return
    UserAuthSession.objects.filter(
        user=user,
        token_key_hash=_hash_token_key(token_key),
        revoked_at__isnull=True,
    ).update(last_seen_at=timezone.now())


def issue_session_after_auth(
    user,
    *,
    request,
    organization=None,
    device_id="",
    remember_device_flag=False,
    ip=None,
    user_agent="",
):
    """Issue API token, track session, optionally trust device. Returns (token, session, flags)."""
    from django.contrib.auth.models import User
    from .authentication import issue_user_token, token_expires_at_iso
    from .tenants import get_profile_for_user

    profile = get_profile_for_user(user, organization=organization)
    org = organization or (profile.organization if profile else None)

    expired = password_is_expired(user, org)
    if expired and profile and not profile.force_password_change:
        profile.force_password_change = True
        profile.save(update_fields=["force_password_change"])

    token = issue_user_token(user)
    session = create_auth_session(
        user,
        token.key,
        organization=org,
        ip=ip,
        user_agent=user_agent,
        device_id=device_id,
    )
    if remember_device_flag and device_id:
        remember_device(
            user,
            device_id,
            organization=org,
            ip=ip,
            user_agent=user_agent,
        )

    User.objects.filter(pk=user.pk).update(last_login=timezone.now())

    suspicious, reason = evaluate_suspicious_login(user, ip, org)
    record_login_event(
        organization=org,
        user=user,
        email=user.email,
        outcome="success",
        ip_address=ip,
        user_agent=user_agent,
        device_id=device_id,
        suspicious=suspicious,
        suspicion_reason=reason,
    )
    return token, session, {
        "must_change_password": bool(expired or (profile and profile.force_password_change)),
        "suspicious": suspicious,
        "suspicion_reason": reason,
        "token_expires_at": token_expires_at_iso(token),
        "device_id": device_id,
        "organization": org,
        "profile": profile,
    }
