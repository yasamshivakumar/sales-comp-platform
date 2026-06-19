import sys

from django.conf import settings

from .models import (
    Commission,
    CompensationPlan,
    Employee,
    Order,
    Organization,
    Sale,
    Territory,
    UserProfile,
)


def get_default_organization():
    org, _ = Organization.objects.get_or_create(
        slug="default",
        defaults={"name": "Default Organization"},
    )
    return org


def allow_default_organization_fallback():
    return (
        getattr(settings, "DEBUG", False)
        or "test" in sys.argv
        or getattr(settings, "TENANT_ALLOW_DEFAULT_FALLBACK", False)
    )


def resolve_request_organization(request):
    """
    Determine tenant from authenticated user's profile.
    Falls back to default org for legacy rows / anonymous health checks.
    """
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        profiles = list(
            UserProfile.objects.filter(email=user.email)
            .select_related("organization")
            [:2]
        )
        profile = profiles[0] if len(profiles) == 1 else None
        if profile and profile.organization_id:
            return profile.organization

    if allow_default_organization_fallback() or not (
        user and getattr(user, "is_authenticated", False)
    ):
        return get_default_organization()
    return None


def filter_queryset_by_organization(queryset, organization, field="organization"):
    if organization is None:
        return queryset.none()
    return queryset.filter(**{field: organization})


def tenant_queryset(model_or_queryset, organization, field="organization"):
    queryset = (
        model_or_queryset.objects.all()
        if hasattr(model_or_queryset, "objects")
        else model_or_queryset
    )
    return filter_queryset_by_organization(queryset, organization, field=field)


def tenant_profiles(organization):
    return tenant_queryset(UserProfile, organization)


def tenant_orders(organization):
    return tenant_queryset(Order, organization)


def tenant_plans(organization):
    return tenant_queryset(CompensationPlan, organization)


def tenant_territories(organization):
    return tenant_queryset(Territory, organization)


def tenant_employees(organization):
    return tenant_queryset(Employee, organization)


def tenant_sales(organization):
    return tenant_queryset(Sale, organization)


def tenant_commissions(organization):
    return tenant_queryset(Commission, organization)


def get_profile_for_user(user, organization=None):
    if not user or not getattr(user, "email", ""):
        return None
    qs = UserProfile.objects.filter(email__iexact=user.email)
    if organization is not None:
        qs = qs.filter(organization=organization)
        return qs.select_related("organization").first()
    profiles = list(qs.select_related("organization")[:2])
    return profiles[0] if len(profiles) == 1 else None


def get_profile_by_email(email, organization=None):
    email = str(email or "").strip()
    if not email:
        return None
    qs = UserProfile.objects.filter(email__iexact=email)
    if organization is not None:
        qs = qs.filter(organization=organization)
        return qs.select_related("organization").first()
    profiles = list(qs.select_related("organization")[:2])
    return profiles[0] if len(profiles) == 1 else None
