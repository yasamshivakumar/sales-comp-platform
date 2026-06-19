from django.conf import settings
from django.http import HttpResponseRedirect
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView
from rest_framework.authtoken.models import Token

from .models import UserProfile
from .tenants import get_default_organization


class TokenOIDCCallbackView(OIDCAuthenticationCallbackView):
    """After SSO, redirect to the React app with an API token."""

    def login_success(self):
        response = super().login_success()
        user = self.request.user
        if not user.is_authenticated:
            return response

        org = get_default_organization()
        profile = UserProfile.objects.filter(email__iexact=user.email, organization=org).first()
        if not profile:
            UserProfile.objects.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                role="Sales Rep",
                organization=org,
                enable_login=True,
            )

        token, _ = Token.objects.get_or_create(user=user)
        frontend = settings.FRONTEND_URL.rstrip("/")
        return HttpResponseRedirect(f"{frontend}/login?token={token.key}")
