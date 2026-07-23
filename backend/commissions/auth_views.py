"""Phase 1.3 auth API endpoints: MFA, sessions, login history, devices."""

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .audit import record_audit
from .auth_hardening import (
    confirm_totp_enrollment,
    consume_mfa_pending_token,
    create_mfa_pending_token,
    issue_session_after_auth,
    mfa_required_for_login,
    record_login_event,
    remember_device,
    revoke_auth_sessions_for_user,
    revoke_trusted_device,
    start_totp_enrollment,
    verify_totp_code,
)
from .models import LoginEvent, TrustedDevice, UserAuthSession, UserMfaDevice
from .permissions import require_admin
from .security import client_ip
from .tenants import get_profile_for_user


def _device_id(request):
    return (
        (request.headers.get("X-Device-Id") or request.data.get("device_id") or "")
        .strip()[:64]
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def mfa_verify(request):
    """Complete login after password step when MFA is required."""
    mfa_token = (request.data.get("mfa_token") or "").strip()
    code = (request.data.get("code") or "").strip()
    remember = bool(request.data.get("remember_device"))
    if not mfa_token or not code:
        return Response(
            {"error": "mfa_token and code are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    pending = consume_mfa_pending_token(mfa_token)
    if not pending:
        return Response(
            {"error": "MFA challenge expired. Sign in again."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    user = User.objects.filter(pk=pending.get("user_id")).first()
    if not user or not user.is_active:
        return Response({"error": "Invalid MFA challenge"}, status=status.HTTP_401_UNAUTHORIZED)

    ip = client_ip(request)
    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:300]
    device_id = _device_id(request) or pending.get("device_id") or ""
    profile = get_profile_for_user(user)
    org = profile.organization if profile else None

    if not verify_totp_code(user, code):
        record_login_event(
            organization=org,
            user=user,
            email=user.email,
            outcome=LoginEvent.OUTCOME_MFA_FAILED,
            ip_address=ip,
            user_agent=user_agent,
            device_id=device_id,
        )
        # Re-issue pending token so user can retry within window
        new_token = create_mfa_pending_token(
            user,
            ip=ip,
            user_agent=user_agent,
            device_id=device_id,
            remember=remember or pending.get("remember"),
        )
        return Response(
            {"error": "Invalid authenticator code", "mfa_token": new_token, "mfa_required": True},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _session, flags = issue_session_after_auth(
        user,
        request=request,
        organization=org,
        device_id=device_id,
        remember_device_flag=remember or pending.get("remember"),
        ip=ip,
        user_agent=user_agent,
    )
    record_audit(
        request,
        "login_success",
        {
            "user_id": user.id,
            "email": user.email,
            "ip": ip,
            "mfa": True,
            "suspicious": flags["suspicious"],
        },
        user=user,
        organization=org,
    )
    return Response(
        {
            "message": "Login successful",
            "token": token.key,
            "token_expires_at": flags["token_expires_at"],
            "email": user.email,
            "user_id": user.id,
            "role": profile.role if profile else "Sales Rep",
            "name": (profile.name if profile else "") or user.get_full_name() or user.username,
            "must_change_password": flags["must_change_password"],
            "suspicious_login": flags["suspicious"],
            "device_id": device_id,
        }
    )


mfa_verify.throttle_scope = "login"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_enroll_start(request):
    device, secret, uri = start_totp_enrollment(
        request.user, name=(request.data.get("name") or "Authenticator")
    )
    record_audit(request, "mfa_enroll_started", {"device_id": device.id})
    return Response(
        {
            "device_id": device.id,
            "secret": secret,
            "otpauth_uri": uri,
            "message": "Scan the QR / enter the secret in your authenticator, then confirm.",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_enroll_confirm(request):
    device_id = request.data.get("device_id")
    code = (request.data.get("code") or "").strip()
    try:
        device_id = int(device_id)
    except (TypeError, ValueError):
        return Response({"error": "device_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    if not confirm_totp_enrollment(request.user, device_id, code):
        return Response({"error": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST)
    remember = bool(request.data.get("remember_device"))
    device_id_hdr = _device_id(request)
    if remember and device_id_hdr:
        remember_device(
            request.user,
            device_id_hdr,
            organization=getattr(request, "organization", None),
            ip=client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:300],
        )
    record_audit(request, "mfa_enroll_confirmed", {"device_id": device_id})
    return Response({"message": "MFA enabled", "mfa_enabled": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mfa_status(request):
    devices = UserMfaDevice.objects.filter(
        user=request.user, is_active=True, confirmed_at__isnull=False
    )
    return Response(
        {
            "mfa_enabled": devices.exists(),
            "devices": [
                {
                    "id": d.id,
                    "name": d.name,
                    "confirmed_at": d.confirmed_at,
                    "last_used_at": d.last_used_at,
                }
                for d in devices
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mfa_disable(request):
    code = (request.data.get("code") or "").strip()
    if not verify_totp_code(request.user, code):
        # Allow disable with password if no confirmed device somehow
        if UserMfaDevice.objects.filter(
            user=request.user, confirmed_at__isnull=False, is_active=True
        ).exists():
            return Response({"error": "Invalid authenticator code"}, status=400)
    UserMfaDevice.objects.filter(user=request.user).update(is_active=False)
    from .models import UserProfile

    UserProfile.objects.filter(email__iexact=request.user.email).update(mfa_enabled=False)
    record_audit(request, "mfa_disabled", {})
    return Response({"message": "MFA disabled", "mfa_enabled": False})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def login_history(request):
    """Current user login history (or org-wide for admins with ?scope=org)."""
    scope = (request.query_params.get("scope") or "me").strip().lower()
    qs = LoginEvent.objects.all()
    org = getattr(request, "organization", None)
    if scope == "org":
        require_admin(request)
        qs = qs.filter(organization=org) if org else qs.none()
    else:
        qs = qs.filter(user=request.user)
    qs = qs[:100]
    return Response(
        {
            "results": [
                {
                    "id": e.id,
                    "email": e.email,
                    "outcome": e.outcome,
                    "ip_address": e.ip_address,
                    "user_agent": e.user_agent,
                    "suspicious": e.suspicious,
                    "suspicion_reason": e.suspicion_reason,
                    "created_at": e.created_at,
                }
                for e in qs
            ]
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def auth_sessions_list(request):
    sessions = UserAuthSession.objects.filter(user=request.user)[:50]
    return Response(
        {
            "results": [
                {
                    "id": s.id,
                    "session_key": s.session_key,
                    "ip_address": s.ip_address,
                    "user_agent": s.user_agent,
                    "device_id": s.device_id,
                    "created_at": s.created_at,
                    "last_seen_at": s.last_seen_at,
                    "revoked_at": s.revoked_at,
                    "active": s.revoked_at is None,
                }
                for s in sessions
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auth_sessions_revoke_all(request):
    revoke_auth_sessions_for_user(request.user, reason="revoke_all")
    record_audit(request, "sessions_revoked_all", {"user_id": request.user.id})
    return Response({"message": "All sessions revoked. Please sign in again."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trusted_devices_list(request):
    devices = TrustedDevice.objects.filter(user=request.user, revoked_at__isnull=True)
    return Response(
        {
            "results": [
                {
                    "id": d.id,
                    "device_id": d.device_id,
                    "device_name": d.device_name,
                    "user_agent": d.user_agent,
                    "last_ip": d.last_ip,
                    "trusted_until": d.trusted_until,
                    "created_at": d.created_at,
                }
                for d in devices
            ]
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trusted_device_revoke(request, device_pk):
    device = TrustedDevice.objects.filter(user=request.user, pk=device_pk).first()
    if not device:
        return Response({"error": "Not found"}, status=404)
    revoke_trusted_device(request.user, device.device_id)
    record_audit(request, "trusted_device_revoked", {"device_id": device.device_id})
    return Response({"message": "Device trust revoked"})
