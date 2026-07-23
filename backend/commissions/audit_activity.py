"""
Enterprise Activity & Compliance Center APIs (extends existing AuditLog).
"""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import record_audit
from .audit_catalog import (
    CRM_SYNC_ACTIONS,
    EXPORT_ACTIONS,
    PAYROLL_ACTIONS,
    action_label,
    resolve_action,
)
from .models import AuditLog
from .permissions import (
    require_finance_or_admin,
    user_has_permission,
    user_is_admin,
)
from .tenants import filter_queryset_by_organization


def require_audit_view(request):
    if user_is_admin(request) or user_has_permission(request, "view_audit"):
        return
    require_finance_or_admin(request)


def require_audit_export(request):
    if user_is_admin(request) or user_has_permission(request, "export_audit"):
        return
    from rest_framework.exceptions import PermissionDenied

    raise PermissionDenied("Only administrators or auditors can export audit activity")


def _parse_dt(value, end_of_day=False):
    from datetime import datetime, time

    raw = (value or "").strip()
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    d = parse_date(raw)
    if d is None:
        return None
    naive = datetime.combine(d, time.max if end_of_day else time.min)
    if timezone.is_aware(timezone.now()):
        return timezone.make_aware(naive)
    return naive


def _base_queryset(request):
    qs = AuditLog.objects.select_related("user", "plan_version", "organization").order_by(
        "-created_at"
    )
    return filter_queryset_by_organization(qs, getattr(request, "organization", None))


def apply_activity_filters(qs, params):
    date_from = _parse_dt(params.get("date_from") or params.get("from"))
    date_to = _parse_dt(params.get("date_to") or params.get("to"), end_of_day=True)
    if date_from:
        qs = qs.filter(created_at__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__lte=date_to)

    module = (params.get("module") or "").strip()
    if module:
        qs = qs.filter(module=module)

    user_q = (params.get("user") or params.get("user_email") or "").strip()
    if user_q:
        qs = qs.filter(user_email__icontains=user_q)

    role = (params.get("role") or "").strip()
    if role:
        qs = qs.filter(role__iexact=role)

    severity = (params.get("severity") or "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    status_f = (params.get("status") or "").strip()
    if status_f:
        qs = qs.filter(status=status_f)

    source = (params.get("source") or "").strip()
    if source:
        qs = qs.filter(source=source)

    action = (params.get("action") or "").strip()
    if action:
        qs = qs.filter(action=action)

    entity_type = (params.get("entity_type") or "").strip()
    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    business_unit = (params.get("business_unit") or "").strip()
    if business_unit:
        qs = qs.filter(business_unit__icontains=business_unit)

    plan_id = (params.get("plan_id") or "").strip()
    if plan_id:
        qs = qs.filter(
            Q(plan_version__compensation_plan_id=plan_id)
            | Q(detail__plan_id=int(plan_id) if plan_id.isdigit() else plan_id)
            | Q(detail__plan_id=plan_id)
            | Q(entity_type="plan", entity_id=plan_id)
        )

    q = (params.get("q") or params.get("search") or "").strip()
    if q:
        qs = qs.filter(
            Q(search_text__icontains=q)
            | Q(user_email__icontains=q)
            | Q(action__icontains=q)
            | Q(employee_id__icontains=q)
            | Q(entity_id__icontains=q)
            | Q(request_id__icontains=q)
            | Q(ip_address__icontains=q)
            | Q(session_id__icontains=q)
            | Q(reason__icontains=q)
        )
    return qs


def serialize_activity_row(row, *, detail_full=False):
    meta = resolve_action(row.action)
    payload = {
        "id": row.id,
        "timestamp": row.created_at.isoformat() if row.created_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "organization_id": row.organization_id,
        "user_id": row.user_id,
        "user_email": row.user_email,
        "employee_id": row.employee_id,
        "role": row.role,
        "business_unit": row.business_unit,
        "module": row.module or meta.get("module") or "",
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "action": row.action,
        "action_label": action_label(row.action),
        "icon": meta.get("icon") or "edit",
        "severity": row.severity or meta.get("severity") or "info",
        "source": row.source or "web",
        "status": row.status or "success",
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "device": row.device or row.user_agent,
        "browser": row.device or "",
        "session_id": row.session_id,
        "correlation_id": row.request_id,
        "request_id": row.request_id,
        "reason": row.reason,
        "changed_fields": row.changed_fields or [],
        "duration_ms": row.duration_ms,
        "plan_version_id": row.plan_version_id,
        "detail": row.detail or {},
    }
    if detail_full:
        payload["old_value"] = row.old_value or {}
        payload["new_value"] = row.new_value or {}
        detail = row.detail if isinstance(row.detail, dict) else {}
        payload["related"] = {
            "user_email": row.user_email,
            "employee_id": row.employee_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "plan_id": detail.get("plan_id")
            or (row.entity_id if row.entity_type == "plan" else None),
            "order_id": detail.get("order_id")
            or (row.entity_id if row.entity_type == "order" else None),
            "profile_id": detail.get("profile_id"),
            "commission_id": detail.get("commission_id"),
            "plan_version_id": row.plan_version_id,
        }
    else:
        # Compact: include change summary keys only
        payload["old_value"] = row.old_value or {}
        payload["new_value"] = row.new_value or {}
    return payload


def _paginate(qs, params):
    # Backward compatible: limit without page
    try:
        page = max(1, int(params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        if params.get("page_size"):
            page_size = min(200, max(1, int(params.get("page_size"))))
        elif params.get("limit"):
            page_size = min(500, max(1, int(params.get("limit"))))
            page = 1
        else:
            page_size = 50
    except (TypeError, ValueError):
        page_size = 50

    total = qs.count()
    start = (page - 1) * page_size
    rows = list(qs[start : start + page_size])
    return total, page, page_size, rows


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    """Activity timeline / table (admin / finance / view_audit)."""
    require_audit_view(request)
    qs = apply_activity_filters(_base_queryset(request), request.query_params)
    total, page, page_size, rows = _paginate(qs, request.query_params)
    data = [serialize_activity_row(row) for row in rows]
    return Response(
        {
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_detail(request, pk):
    require_audit_view(request)
    row = _base_queryset(request).filter(pk=pk).first()
    if not row:
        return Response({"error": "Activity not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(serialize_activity_row(row, detail_full=True))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_summary(request):
    require_audit_view(request)
    org = getattr(request, "organization", None)
    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    qs = filter_queryset_by_organization(
        AuditLog.objects.filter(created_at__gte=start), org
    )
    security_q = Q(module="authentication") | Q(action__in=list(
        {
            "login_failed",
            "login_locked_out",
            "role_changed",
            "permission_changed",
            "password_changed",
            "mfa_disabled",
            "api_key_created",
            "api_key_deleted",
            "settings_changed",
        }
    ))
    return Response(
        {
            "today_activities": qs.count(),
            "critical_events": qs.filter(severity=AuditLog.SEVERITY_CRITICAL).count(),
            "security_events": qs.filter(security_q).count(),
            "failed_actions": qs.filter(status=AuditLog.STATUS_FAILED).count(),
            "exports": qs.filter(
                Q(action__in=list(EXPORT_ACTIONS)) | Q(source="web", action__icontains="export")
            ).count(),
            "crm_syncs": qs.filter(
                Q(action__in=list(CRM_SYNC_ACTIONS))
                | Q(action__startswith="integration_sync")
                | Q(module="crm_integrations", action__icontains="sync")
            ).count(),
            "payroll_runs": qs.filter(
                Q(action__in=list(PAYROLL_ACTIONS)) | Q(module="payroll") | Q(module="payouts")
            ).count(),
            "as_of": now.isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_security(request):
    require_audit_view(request)
    qs = apply_activity_filters(_base_queryset(request), request.query_params)
    qs = qs.filter(
        Q(module="authentication")
        | Q(status=AuditLog.STATUS_FAILED)
        | Q(
            action__in=[
                "login_failed",
                "login_locked_out",
                "role_changed",
                "permission_changed",
                "password_changed",
                "mfa_disabled",
                "sessions_revoked_all",
                "api_key_created",
                "api_key_deleted",
                "settings_changed",
            ]
        )
    )
    total, page, page_size, rows = _paginate(qs, request.query_params)
    return Response(
        {
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": [serialize_activity_row(row) for row in rows],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_export(request):
    require_audit_export(request)
    qs = apply_activity_filters(_base_queryset(request), request.query_params)
    # Cap export size
    rows = list(qs[:5000])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "timestamp",
            "user_email",
            "employee_id",
            "role",
            "module",
            "action",
            "severity",
            "status",
            "source",
            "entity_type",
            "entity_id",
            "changed_fields",
            "reason",
            "ip_address",
            "device",
            "session_id",
            "correlation_id",
            "old_value",
            "new_value",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.created_at.isoformat() if row.created_at else "",
                row.user_email,
                row.employee_id,
                row.role,
                row.module,
                row.action,
                row.severity,
                row.status,
                row.source,
                row.entity_type,
                row.entity_id,
                ",".join(row.changed_fields or []),
                row.reason,
                row.ip_address or "",
                row.device,
                row.session_id,
                row.request_id,
                str(row.old_value or {}),
                str(row.new_value or {}),
            ]
        )

    record_audit(
        request,
        "audit_export",
        {
            "row_count": len(rows),
            "filters": {k: request.query_params.get(k) for k in request.query_params},
        },
        source=AuditLog.SOURCE_WEB,
        severity=AuditLog.SEVERITY_INFO,
        entity_type="audit",
    )

    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="activity-compliance-export.csv"'
    return response
