import logging
import re
import uuid

from .models import AuditLog

logger = logging.getLogger("commissions")


def get_client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_request_id(request):
    if request is None:
        return ""
    return getattr(request, "request_id", None) or request.META.get("HTTP_X_REQUEST_ID", "")


def get_user_agent(request):
    if request is None:
        return ""
    return (request.META.get("HTTP_USER_AGENT") or "")[:512]


def infer_device(user_agent):
    ua = (user_agent or "").lower()
    if not ua:
        return ""
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "Mobile"
    if "ipad" in ua or "tablet" in ua:
        return "Tablet"
    if "edg/" in ua:
        return "Edge"
    if "chrome" in ua and "edg/" not in ua:
        return "Chrome"
    if "firefox" in ua:
        return "Firefox"
    if "safari" in ua:
        return "Safari"
    return "Browser"


def diff_fields(old_value, new_value):
    """Return sorted list of keys that differ between two dict-like payloads."""
    old = old_value if isinstance(old_value, dict) else {}
    new = new_value if isinstance(new_value, dict) else {}
    keys = set(old) | set(new)
    changed = []
    for key in keys:
        if old.get(key) != new.get(key):
            changed.append(str(key))
    return sorted(changed)


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


def _profile_snapshot(actor, email="", organization=None):
    from .tenants import get_profile_for_user, get_profile_by_email

    profile = None
    if actor is not None:
        profile = get_profile_for_user(actor, organization=organization)
    if profile is None and email:
        profile = get_profile_by_email(email, organization=organization)
    if not profile:
        return {"employee_id": "", "role": "", "business_unit": ""}
    return {
        "employee_id": str(getattr(profile, "employee_id", "") or ""),
        "role": str(getattr(profile, "role", "") or ""),
        "business_unit": str(
            getattr(profile, "business_group", "")
            or getattr(profile, "department", "")
            or ""
        ),
    }


def _session_id_from_request(request, explicit=None):
    if explicit:
        return str(explicit)[:64]
    if request is None:
        return ""
    # Prefer DRF token key fragment (stable per session) over Django session.
    auth = getattr(request, "auth", None)
    if auth is not None and getattr(auth, "key", None):
        return str(auth.key)[:64]
    device = request.META.get("HTTP_X_DEVICE_ID") or ""
    if device:
        return str(device)[:64]
    session = getattr(request, "session", None)
    if session is not None:
        try:
            key = session.session_key
            if key:
                return str(key)[:64]
        except Exception:
            pass
    return ""


def _infer_source(request, source=None, action=""):
    if source:
        return source
    key = str(action or "")
    if "upload" in key or key.endswith("_csv") or "csv" in key:
        return AuditLog.SOURCE_CSV
    if key.startswith("integration_sync") or key.startswith("crm_sync"):
        return AuditLog.SOURCE_CRM
    if "queued" in key or key.endswith("_job"):
        return AuditLog.SOURCE_JOB
    if request is None:
        return AuditLog.SOURCE_JOB
    path = getattr(request, "path", "") or ""
    if path.startswith("/api/") and "HTTP_AUTHORIZATION" in getattr(request, "META", {}):
        # Prefer web for browser SPA token calls; treat as API only when no UA.
        ua = get_user_agent(request)
        if not ua:
            return AuditLog.SOURCE_API
    return AuditLog.SOURCE_WEB


def _infer_status(action, status=None, detail=None):
    if status:
        return status
    key = str(action or "")
    if key in ("login_failed", "login_locked_out", "crm_sync_failed") or key.endswith("_failed"):
        return AuditLog.STATUS_FAILED
    if "cancel" in key:
        return AuditLog.STATUS_CANCELLED
    if isinstance(detail, dict) and detail.get("error"):
        return AuditLog.STATUS_FAILED
    return AuditLog.STATUS_SUCCESS


def _entity_from_detail(detail, entity_type="", entity_id=""):
    if not isinstance(detail, dict):
        return entity_type or "", str(entity_id or "")
    et = entity_type or str(
        detail.get("entity_type")
        or ("plan" if detail.get("plan_id") else "")
        or ("order" if detail.get("order_id") else "")
        or ("user" if detail.get("profile_id") else "")
        or ""
    )
    eid = entity_id or detail.get("entity_id") or detail.get("plan_id") or detail.get(
        "order_id"
    ) or detail.get("profile_id") or detail.get("commission_id") or detail.get(
        "integration_id"
    ) or ""
    return et, str(eid) if eid not in (None, "") else ""


def _legacy_from_to(detail):
    """Lift ad-hoc from/to detail keys into old/new value dicts."""
    if not isinstance(detail, dict):
        return {}, {}
    old, new = {}, {}
    if "from" in detail or "to" in detail:
        field = detail.get("field") or "value"
        if "from" in detail:
            old[field] = detail.get("from")
        if "to" in detail:
            new[field] = detail.get("to")
    for key in ("old", "before", "previous"):
        if isinstance(detail.get(key), dict):
            old.update(detail[key])
    for key in ("new", "after", "current"):
        if isinstance(detail.get(key), dict):
            new.update(detail[key])
    return old, new


def _build_search_text(**parts):
    chunks = []
    for value in parts.values():
        if value in (None, "", {}, []):
            continue
        if isinstance(value, (dict, list)):
            chunks.append(re.sub(r"\s+", " ", str(value))[:500])
        else:
            chunks.append(str(value))
    return " ".join(chunks)[:4000]


def record_audit(
    request,
    action,
    detail=None,
    plan_version=None,
    *,
    user=None,
    organization=None,
    module=None,
    entity_type=None,
    entity_id=None,
    severity=None,
    source=None,
    status=None,
    reason=None,
    old_value=None,
    new_value=None,
    changed_fields=None,
    duration_ms=None,
    session_id=None,
):
    """Persist an audit row; never raises to callers.

    Pass ``user`` / ``organization`` for unauthenticated flows (login) where
    ``request.user`` is still AnonymousUser and TenantMiddleware may have
    attached the default org instead of the actor's real tenant.
    """
    try:
        from .audit_catalog import resolve_action

        actor = user
        if actor is None and request is not None:
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

        org = organization
        if org is None:
            org = _organization_for_actor(actor)
        if org is None:
            org = _organization_for_email(user_email)
        if org is None and request is not None:
            org = getattr(request, "organization", None)

        meta = resolve_action(action)
        snap = _profile_snapshot(actor, email=user_email, organization=org)
        safe_detail = _safe_audit_detail(detail)

        legacy_old, legacy_new = _legacy_from_to(safe_detail)
        old_payload = _safe_audit_detail(old_value) if old_value is not None else legacy_old
        new_payload = _safe_audit_detail(new_value) if new_value is not None else legacy_new
        if not isinstance(old_payload, dict):
            old_payload = {}
        if not isinstance(new_payload, dict):
            new_payload = {}

        fields = changed_fields
        if fields is None:
            fields = diff_fields(old_payload, new_payload)
        if not isinstance(fields, list):
            fields = list(fields) if fields else []

        et, eid = _entity_from_detail(
            safe_detail, entity_type or meta.get("entity_type") or "", entity_id or ""
        )
        user_agent = get_user_agent(request)
        resolved_status = _infer_status(action, status, safe_detail)
        resolved_severity = severity or meta.get("severity") or AuditLog.SEVERITY_INFO
        if resolved_status == AuditLog.STATUS_FAILED and resolved_severity == AuditLog.SEVERITY_INFO:
            resolved_severity = AuditLog.SEVERITY_WARNING

        reason_text = reason or ""
        if not reason_text and isinstance(safe_detail, dict):
            reason_text = str(safe_detail.get("reason") or safe_detail.get("comment") or "")

        sid = _session_id_from_request(request, session_id)
        rid = get_request_id(request) or str(uuid.uuid4())
        search = _build_search_text(
            email=user_email,
            action=action,
            module=module or meta.get("module"),
            employee_id=snap["employee_id"],
            entity_type=et,
            entity_id=eid,
            ip=get_client_ip(request),
            request_id=rid,
            session_id=sid,
            reason=reason_text,
            changed=",".join(fields),
        )

        AuditLog.objects.create(
            organization=org,
            user_id=user_id,
            user_email=user_email,
            employee_id=snap["employee_id"],
            role=snap["role"],
            business_unit=snap["business_unit"],
            action=action,
            module=module or meta.get("module") or "",
            entity_type=et,
            entity_id=eid,
            severity=resolved_severity,
            source=_infer_source(request, source, action),
            status=resolved_status,
            plan_version=plan_version,
            detail=safe_detail if isinstance(safe_detail, dict) else {},
            reason=reason_text[:4000],
            old_value=old_payload,
            new_value=new_payload,
            changed_fields=fields,
            duration_ms=duration_ms,
            ip_address=get_client_ip(request) or None,
            user_agent=user_agent,
            device=infer_device(user_agent),
            session_id=sid,
            request_id=rid,
            search_text=search,
        )
    except Exception:
        logger.exception("Failed to write audit log for action=%s", action)


def _safe_audit_detail(detail):
    if detail is None:
        return {}
    try:
        from .credential_crypto import redact_secrets

        return redact_secrets(detail)
    except Exception:
        if isinstance(detail, dict):
            return {"_redacted": True}
        return {}
