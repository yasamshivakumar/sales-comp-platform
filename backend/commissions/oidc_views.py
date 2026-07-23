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
from .tenants import resolve_organization_for_oidc

logger = logging.getLogger("commissions")

OIDC_EXCHANGE_PREFIX = "oidc_exchange:"
OIDC_EXCHANGE_TTL_SECONDS = 120


def _oidc_claims(request, user):
    """Best-effort claim dict from mozilla-django-oidc session / user attrs."""
    claims = {}
    for key in (
        "oidc_user_info",
        "oidc_id_token_payload",
        "userinfo",
    ):
        raw = request.session.get(key) if hasattr(request, "session") else None
        if isinstance(raw, dict):
            claims.update(raw)
    # Common extras sometimes stored on the user by the backend
    for attr in ("organization_slug", "organization", "org"):
        val = getattr(user, attr, None)
        if val:
            claims.setdefault(attr, val)
    return claims


class TokenOIDCCallbackView(OIDCAuthenticationCallbackView):
    """After SSO, redirect to the React app with a one-time exchange code."""

    def login_success(self):
        response = super().login_success()
        user = self.request.user
        if not user.is_authenticated:
            return response

        claims = _oidc_claims(self.request, user)
        org, source = resolve_organization_for_oidc(email=user.email, claims=claims)
        if org is None:
            logger.error(
                "OIDC login failed: no organization resolved for %s (source=%s)",
                user.email,
                source,
            )
            frontend = settings.FRONTEND_URL.rstrip("/")
            return HttpResponseRedirect(f"{frontend}/login?sso_error=org")

        profile = UserProfile.objects.filter(
            email__iexact=user.email, organization=org
        ).first()
        if not profile:
            # Do not auto-create profiles in a different org when email already
            # belongs to another tenant.
            other = UserProfile.objects.filter(email__iexact=user.email).exclude(
                organization=org
            ).exists()
            if other:
                logger.error(
                    "OIDC login refused: %s already provisioned in another organization",
                    user.email,
                )
                frontend = settings.FRONTEND_URL.rstrip("/")
                return HttpResponseRedirect(f"{frontend}/login?sso_error=org")
            UserProfile.objects.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                role="Sales Rep",
                organization=org,
                enable_login=True,
            )
            logger.info(
                "OIDC provisioned profile for %s in org=%s via %s",
                user.email,
                org.slug,
                source,
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
