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


def record_audit(request, action, detail=None, plan_version=None):
    """Persist an audit row; never raises to callers."""
    try:
        user = getattr(request, "user", None)
        user_email = ""
        user_id = None
        if user and getattr(user, "is_authenticated", False):
            user_email = getattr(user, "email", "") or ""
            user_id = user.pk

        organization = getattr(request, "organization", None)

        AuditLog.objects.create(
            organization=organization,
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
