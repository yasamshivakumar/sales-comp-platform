from rest_framework.authentication import TokenAuthentication

from .tenants import get_profile_for_user


class TenantTokenAuthentication(TokenAuthentication):
    """Token auth that resolves the tenant after DRF authenticates the user."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if not result:
            return result

        user, token = result
        profile = get_profile_for_user(user)
        request.organization = profile.organization if profile else None
        return user, token
