from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .tenants import get_profile_for_user


def token_ttl_minutes(organization=None):
    from .auth_hardening import effective_token_ttl_minutes

    return effective_token_ttl_minutes(organization)


def is_token_expired(token, organization=None):
    ttl_minutes = token_ttl_minutes(organization)
    if not ttl_minutes:
        return False
    return token.created < timezone.now() - timedelta(minutes=ttl_minutes)


def issue_user_token(user):
    """Return a fresh API token for the user, replacing any stale token."""
    Token.objects.filter(user=user).delete()
    return Token.objects.create(user=user)


def token_expires_at(token, organization=None):
    ttl_minutes = token_ttl_minutes(organization)
    if not ttl_minutes:
        return None
    return token.created + timedelta(minutes=ttl_minutes)


def token_expires_at_iso(token, organization=None):
    expires_at = token_expires_at(token, organization=organization)
    return expires_at.isoformat() if expires_at else None


def touch_token_for_activity(token, organization=None):
    """
    Sliding idle timeout: each authenticated request can extend the session.
    Writes are throttled so busy APIs do not update the row every request.
    """
    ttl_minutes = token_ttl_minutes(organization)
    if not ttl_minutes:
        return token

    now = timezone.now()
    refresh_after = timedelta(minutes=min(2, max(ttl_minutes // 12, 1)))
    if now - token.created < refresh_after:
        return token

    Token.objects.filter(pk=token.pk).update(created=now)
    token.created = now
    return token


class TenantTokenAuthentication(TokenAuthentication):
    """Token auth that resolves the tenant after DRF authenticates the user."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return result

        user, token = result
        profile = get_profile_for_user(user)
        organization = profile.organization if profile else None
        request.organization = organization

        if is_token_expired(token, organization=organization):
            token.delete()
            raise AuthenticationFailed("Session expired. Please sign in again.")

        token = touch_token_for_activity(token, organization=organization)
        request.session_expires_at = token_expires_at_iso(token, organization=organization)
        request.force_password_change = bool(
            profile and (profile.force_password_change or False)
        )
        try:
            from .auth_hardening import password_is_expired, touch_auth_session_for_token

            if password_is_expired(user, organization):
                request.force_password_change = True
            touch_auth_session_for_token(user, token.key)
        except Exception:
            pass
        return user, token
