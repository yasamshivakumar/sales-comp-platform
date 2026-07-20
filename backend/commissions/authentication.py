from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .tenants import get_profile_for_user


def token_ttl_minutes():
    return getattr(settings, "TOKEN_TTL_MINUTES", 480)


def is_token_expired(token):
    ttl_minutes = token_ttl_minutes()
    if not ttl_minutes:
        return False
    return token.created < timezone.now() - timedelta(minutes=ttl_minutes)


def issue_user_token(user):
    """Return a fresh API token for the user, replacing any stale token."""
    Token.objects.filter(user=user).delete()
    return Token.objects.create(user=user)


def token_expires_at(token):
    ttl_minutes = token_ttl_minutes()
    if not ttl_minutes:
        return None
    return token.created + timedelta(minutes=ttl_minutes)


def token_expires_at_iso(token):
    expires_at = token_expires_at(token)
    return expires_at.isoformat() if expires_at else None


def touch_token_for_activity(token):
    """
    Sliding idle timeout: each authenticated request can extend the session.
    Writes are throttled so busy APIs do not update the row every call.
    """
    ttl_minutes = token_ttl_minutes()
    if not ttl_minutes:
        return token

    now = timezone.now()
    # Refresh at most every 2 minutes (or sooner for very short TTLs).
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
        if is_token_expired(token):
            token.delete()
            raise AuthenticationFailed("Session expired. Please sign in again.")

        token = touch_token_for_activity(token)
        request.session_expires_at = token_expires_at_iso(token)

        profile = get_profile_for_user(user)
        request.organization = profile.organization if profile else None
        return user, token
