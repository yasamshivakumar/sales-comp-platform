from rest_framework.exceptions import PermissionDenied

from .models import UserProfile


def get_request_user_profile(request):
    try:
        return UserProfile.objects.get(email=request.user.email)
    except UserProfile.DoesNotExist:
        return None


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


def user_can_view_finance_data(request):
    return user_is_admin(request) or user_is_finance(request)


def require_admin(request):
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can perform this action")


def require_finance_or_admin(request):
    if not user_can_view_finance_data(request):
        raise PermissionDenied(
            "Only administrators or finance users can access this resource"
        )


def require_manager_or_admin(request):
    if not (user_is_manager(request) or user_is_admin(request)):
        raise PermissionDenied(
            "Only managers or administrators can perform this action"
        )
