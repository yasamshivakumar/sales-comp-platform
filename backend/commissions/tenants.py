import logging

from django.conf import settings
from django.db import DatabaseError, OperationalError
from django.db.models import Q

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

logger = logging.getLogger("commissions")


def get_default_organization():
    try:
        org, _ = Organization.objects.get_or_create(
            slug="default",
            defaults={"name": "Default Organization"},
        )
        return org
    except (DatabaseError, OperationalError) as exc:
        logger.warning("Could not resolve default organization: %s", exc)
        return None


def allow_default_organization_fallback():
    """
    Legacy null-org / default-org escape hatch.

    Controlled by ``TENANT_ALLOW_DEFAULT_FALLBACK`` (True in DEBUG/tests by
    default; False in production). Security tests can override_settings to False.
    """
    return bool(getattr(settings, "TENANT_ALLOW_DEFAULT_FALLBACK", False))


def resolve_request_organization(request):
    """
    Determine tenant from authenticated user's profile.

    Authenticated users never receive the default organization unless
    ``allow_default_organization_fallback()`` is true (DEBUG/tests).
    Anonymous requests may use default org only when fallback is allowed
    (health checks / legacy).
    """
    user = getattr(request, "user", None)
    authenticated = bool(user and getattr(user, "is_authenticated", False))

    if authenticated:
        profiles = list(
            UserProfile.objects.filter(email__iexact=user.email)
            .select_related("organization")[:2]
        )
        profile = profiles[0] if len(profiles) == 1 else None
        if profile and profile.organization_id:
            return profile.organization
        # Ambiguous or missing org: fail closed in production.
        if allow_default_organization_fallback():
            return get_default_organization()
        return None

    if allow_default_organization_fallback():
        return get_default_organization()
    return None


def filter_queryset_by_organization(queryset, organization, field="organization"):
    if organization is None:
        return queryset.none()
    return queryset.filter(**{field: organization})


def tenant_org_q(organization, field="organization"):
    """
    Build a Q for org scoping. Includes null-org rows only when fallback is on.
    """
    if organization is None:
        if allow_default_organization_fallback():
            return Q(**{f"{field}__isnull": True})
        return Q(pk__in=[])
    q = Q(**{field: organization})
    if allow_default_organization_fallback():
        q = q | Q(**{f"{field}__isnull": True})
    return q


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


def resolve_organization_for_oidc(*, email="", claims=None):
    """
    Resolve tenant for SSO login from IdP claims or email-domain map.

    Returns (organization, source) where source is claim|domain|default|none.
    Never creates an organization here.
    """
    claims = claims or {}
    claim_name = getattr(settings, "OIDC_ORGANIZATION_CLAIM", "organization_slug") or "organization_slug"
    slug = str(claims.get(claim_name) or claims.get("organization") or "").strip()
    if slug:
        org = Organization.objects.filter(slug__iexact=slug).first()
        if org:
            return org, "claim"

    domain_map = getattr(settings, "OIDC_EMAIL_DOMAIN_ORG_MAP", None) or {}
    email = str(email or "").strip().lower()
    if "@" in email and domain_map:
        domain = email.split("@", 1)[1]
        mapped = domain_map.get(domain)
        if mapped:
            org = Organization.objects.filter(slug__iexact=mapped).first()
            if org:
                return org, "domain"

    if allow_default_organization_fallback():
        org = get_default_organization()
        return org, "default" if org else "none"

    # Production: only attach to default org when the email already has a
    # profile there — never create ambiguous cross-tenant profiles.
    default_org = Organization.objects.filter(slug="default").first()
    if default_org and email:
        if UserProfile.objects.filter(
            email__iexact=email, organization=default_org
        ).exists():
            return default_org, "existing_profile"
    return None, "none"
