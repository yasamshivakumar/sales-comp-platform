from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated


def get_request_user_profile(request):
    from .tenants import get_profile_for_user

    return get_profile_for_user(
        request.user,
        organization=getattr(request, "organization", None),
    )


def _normalized_role(request):
    profile = get_request_user_profile(request)
    if not profile or not profile.role:
        return ""
    return str(profile.role).strip().lower()


def user_is_admin(request):
    return _normalized_role(request) in ("admin", "administrator")


def user_is_finance(request):
    return _normalized_role(request) in (
        "finance",
        "finance viewer",
        "finance admin",
    )


def user_is_manager(request):
    return _normalized_role(request) in (
        "manager",
        "sales manager",
    )


def effective_permission_codes(profile):
    """Resolve permission codes for a profile (role defaults or custom matrix)."""
    from .people_ops import permissions_for_role

    if profile is None:
        return set()
    custom = getattr(profile, "custom_permissions", None)
    if isinstance(custom, list):
        # Explicit People UI matrix is authoritative when present (incl. empty).
        return set(permissions_for_role(profile.role, custom_permissions=custom))
    return set(permissions_for_role(profile.role, custom_permissions=None))


def user_has_permission(request, code):
    """True if the caller's effective permission set includes ``code``."""
    profile = get_request_user_profile(request)
    if not profile:
        return False
    return str(code) in effective_permission_codes(profile)


def user_can_view_finance_data(request):
    # Preserve legacy role aliases; do not expand Manager via catalog alone.
    return user_is_admin(request) or user_is_finance(request)


def require_admin(request):
    """Admin role OR custom matrix with manage_users / manage_plans."""
    if user_is_admin(request):
        return
    profile = get_request_user_profile(request)
    if profile and isinstance(getattr(profile, "custom_permissions", None), list):
        codes = effective_permission_codes(profile)
        if codes & {"manage_users", "manage_plans"}:
            return
    raise PermissionDenied("Only administrators can perform this action")


def require_finance_or_admin(request):
    """Admin/Finance roles OR custom matrix with finance-capable codes."""
    if user_is_admin(request) or user_is_finance(request):
        return
    profile = get_request_user_profile(request)
    if profile and isinstance(getattr(profile, "custom_permissions", None), list):
        codes = effective_permission_codes(profile)
        if codes & {
            "export_reports",
            "view_commissions",
            "approve_transactions",
            "manage_users",
            "manage_plans",
        }:
            return
    raise PermissionDenied(
        "Only administrators or finance users can access this resource"
    )


def require_permission(request, code, message=None):
    if user_is_admin(request):
        return
    if user_has_permission(request, code):
        return
    raise PermissionDenied(message or f"Missing permission: {code}")


_FORCE_PASSWORD_CHANGE_ALLOWLIST = (
    "/api/auth/change-password",
    "/api/auth/logout",
    "/api/auth/session",
    "/api/user-profile",
    "/api/auth/mfa/",
)


class IsAuthenticatedAndPasswordCurrent(IsAuthenticated):
    """Block API use when the user must change an expired password."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not getattr(request, "force_password_change", False):
            return True
        path = (request.path or "").rstrip("/")
        for allowed in _FORCE_PASSWORD_CHANGE_ALLOWLIST:
            base = allowed.rstrip("/")
            if path == base or path.startswith(base):
                return True
        return False
