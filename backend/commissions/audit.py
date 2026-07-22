import logging
import uuid

from .models import AuditLog

logger = logging.getLogger("commissions")


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_request_id(request):
    return getattr(request, "request_id", None) or request.META.get("HTTP_X_REQUEST_ID", "")


def _organization_for_actor(actor):
    if actor is None:
        return None
    from .tenants import get_profile_for_user

    profile = get_profile_for_user(actor)
    return profile.organization if profile else None


def _organization_for_email(email):
    email = str(email or "").strip()
    if not email:
        return None
    from .models import UserProfile

    profile = (
        UserProfile.objects.filter(email__iexact=email)
        .select_related("organization")
        .first()
    )
    return profile.organization if profile else None


def record_audit(
    request,
    action,
    detail=None,
    plan_version=None,
    *,
    user=None,
    organization=None,
):
    """Persist an audit row; never raises to callers.

    Pass ``user`` / ``organization`` for unauthenticated flows (login) where
    ``request.user`` is still AnonymousUser and TenantMiddleware may have
    attached the default org instead of the actor's real tenant.
    """
    try:
        actor = user
        if actor is None:
            candidate = getattr(request, "user", None)
            if candidate and getattr(candidate, "is_authenticated", False):
                actor = candidate

        user_email = ""
        user_id = None
        if actor is not None:
            user_email = (
                getattr(actor, "email", "")
                or getattr(actor, "username", "")
                or ""
            )
            user_id = actor.pk
        elif isinstance(detail, dict):
            user_email = str(
                detail.get("email") or detail.get("username") or ""
            )

        # Resolve tenant: explicit override → actor profile → email profile
        # → request.organization (middleware). Never leave known users on the
        # anonymous default-org fallback from login endpoints.
        org = organization
        if org is None:
            org = _organization_for_actor(actor)
        if org is None:
            org = _organization_for_email(user_email)
        if org is None:
            org = getattr(request, "organization", None)

        AuditLog.objects.create(
            organization=org,
            user_id=user_id,
            user_email=user_email,
            action=action,
            plan_version=plan_version,
            detail=detail or {},
            ip_address=get_client_ip(request) or None,
            request_id=get_request_id(request) or str(uuid.uuid4()),
        )
    except Exception:
        logger.exception("Failed to write audit log for action=%s", action)
