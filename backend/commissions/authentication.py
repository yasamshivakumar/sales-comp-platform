from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .tenants import get_profile_for_user


class TenantTokenAuthentication(TokenAuthentication):
    """Token auth that resolves the tenant after DRF authenticates the user."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return result

        user, token = result
        ttl_minutes = getattr(settings, "TOKEN_TTL_MINUTES", 480)
        if ttl_minutes and token.created < timezone.now() - timedelta(minutes=ttl_minutes):
            token.delete()
            raise AuthenticationFailed("Session expired. Please sign in again.")

        profile = get_profile_for_user(user)
        request.organization = profile.organization if profile else None
        return user, token


def token_expires_at(token):
    ttl_minutes = getattr(settings, "TOKEN_TTL_MINUTES", 480)
    if not ttl_minutes:
        return None
    return token.created + timedelta(minutes=ttl_minutes)
