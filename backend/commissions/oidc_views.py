import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from rest_framework.authtoken.models import Token

from .authentication import issue_user_token, token_expires_at_iso
from .models import UserProfile
from .tenants import get_default_organization

logger = logging.getLogger("commissions")

OIDC_EXCHANGE_PREFIX = "oidc_exchange:"
OIDC_EXCHANGE_TTL_SECONDS = 120


class TokenOIDCCallbackView(OIDCAuthenticationCallbackView):
    """After SSO, redirect to the React app with a one-time exchange code."""

    def login_success(self):
        response = super().login_success()
        user = self.request.user
        if not user.is_authenticated:
            return response

        org = get_default_organization()
        if org is None:
            logger.error("OIDC login failed: default organization is unavailable")
            frontend = settings.FRONTEND_URL.rstrip("/")
            return HttpResponseRedirect(f"{frontend}/login?sso_error=org")

        profile = UserProfile.objects.filter(
            email__iexact=user.email, organization=org
        ).first()
        if not profile:
            UserProfile.objects.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                role="Sales Rep",
                organization=org,
                enable_login=True,
            )

        token = issue_user_token(user)
        code = secrets.token_urlsafe(32)
        cache.set(f"{OIDC_EXCHANGE_PREFIX}{code}", token.key, timeout=OIDC_EXCHANGE_TTL_SECONDS)
        frontend = settings.FRONTEND_URL.rstrip("/")
        return HttpResponseRedirect(f"{frontend}/login?sso_code={code}")


class OidcExchangeThrottle(ScopedRateThrottle):
    scope = "oidc_exchange"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OidcExchangeThrottle])
def oidc_token_exchange(request):
    """Exchange a one-time SSO code for an API token (never put tokens in URLs)."""
    code = (request.data.get("code") or request.data.get("sso_code") or "").strip()
    if not code:
        return Response(
            {"error": "Exchange code is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cache_key = f"{OIDC_EXCHANGE_PREFIX}{code}"
    token_key = cache.get(cache_key)
    if not token_key:
        return Response(
            {"error": "Invalid or expired sign-in code"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cache.delete(cache_key)
    token = Token.objects.filter(key=token_key).first()
    payload = {"token": token_key}
    if token:
        payload["token_expires_at"] = token_expires_at_iso(token)
    return Response(payload)
