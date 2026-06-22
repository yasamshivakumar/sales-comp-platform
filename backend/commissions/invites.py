"""Invite-based login activation helpers."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from .auth_utils import provision_login_user
from .emails import notify_user
from .models import UserInvite


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_ttl():
    hours = int(getattr(settings, "INVITE_TOKEN_TTL_HOURS", 72))
    return timedelta(hours=hours)


def build_invite_url(token):
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{frontend}/invite/{token}"


def create_user_invite(profile, *, invited_by=None, send_email=True):
    if not profile or not profile.enable_login:
        return None, "", False

    email = (profile.email or "").strip().lower()
    if not email:
        return None, "", False

    provision_login_user(profile, pending_invite=True)
    now = timezone.now()
    UserInvite.objects.filter(
        user_profile=profile,
        accepted_at__isnull=True,
        expires_at__gt=now,
    ).update(expires_at=now)

    token = secrets.token_urlsafe(32)
    invite = UserInvite.objects.create(
        organization=profile.organization,
        user_profile=profile,
        invited_by=invited_by if getattr(invited_by, "is_authenticated", False) else None,
        email=email,
        token_hash=_hash_token(token),
        expires_at=now + invite_ttl(),
    )

    sent = False
    if send_email:
        sent = send_invite_email(invite, token)
        if sent:
            invite.sent_at = timezone.now()
            invite.save(update_fields=["sent_at", "updated_at"])

    return invite, token, sent


def send_invite_email(invite, token):
    profile = invite.user_profile
    url = build_invite_url(token)
    org_name = invite.organization.name if invite.organization_id else "Incentra"
    display_name = profile.name or profile.first_name or profile.email
    message = (
        f"Hi {display_name},\n\n"
        f"You have been invited to join {org_name} on Incentra.\n\n"
        "Set your password using this secure link:\n"
        f"{url}\n\n"
        f"This invite expires on {invite.expires_at:%Y-%m-%d %H:%M UTC}.\n"
        "If you did not expect this invite, ignore this email."
    )
    return notify_user(
        invite.email,
        f"[Incentra] You're invited to {org_name}",
        message,
    )


def get_valid_invite(token):
    token_hash = _hash_token(str(token or "").strip())
    if not token_hash:
        return None
    invite = (
        UserInvite.objects.select_related("organization", "user_profile")
        .filter(token_hash=token_hash)
        .first()
    )
    if not invite or invite.accepted_at:
        return None
    if invite.expires_at <= timezone.now():
        return None
    return invite


def invite_context(invite):
    profile = invite.user_profile
    return {
        "email": invite.email,
        "name": profile.name or profile.first_name or invite.email,
        "employee_id": profile.employee_id,
        "role": profile.role,
        "organization_name": invite.organization.name if invite.organization_id else "",
        "expires_at": invite.expires_at.isoformat(),
    }


def accept_invite(token, password):
    invite = get_valid_invite(token)
    if not invite:
        return None

    profile = invite.user_profile
    profile.enable_login = True
    profile.save(update_fields=["enable_login"])

    user = provision_login_user(profile, pending_invite=True)
    user.set_password(password)
    user.is_active = True
    user.save()

    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_at", "updated_at"])
    UserInvite.objects.filter(
        user_profile=profile,
        accepted_at__isnull=True,
    ).exclude(pk=invite.pk).update(expires_at=timezone.now())

    return user


def user_has_pending_invite(user):
    if not isinstance(user, User):
        return False
    return UserInvite.objects.filter(
        email__iexact=user.email,
        accepted_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists()
