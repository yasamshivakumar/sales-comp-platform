from .models import Organization, UserProfile


def get_default_organization():
    org, _ = Organization.objects.get_or_create(
        slug="default",
        defaults={"name": "Default Organization"},
    )
    return org


def resolve_request_organization(request):
    """
    Determine tenant from authenticated user's profile.
    Falls back to default org for legacy rows / anonymous health checks.
    """
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        profile = (
            UserProfile.objects.filter(email=user.email)
            .select_related("organization")
            .first()
        )
        if profile and profile.organization_id:
            return profile.organization

    return get_default_organization()


def filter_queryset_by_organization(queryset, organization, field="organization"):
    if organization is None:
        return queryset
    return queryset.filter(**{field: organization})
