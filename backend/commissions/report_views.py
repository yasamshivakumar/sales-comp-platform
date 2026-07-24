"""
Self-service Report Builder APIs — catalog, wizard preview, run, schedule.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import record_audit
from .models import Report, ReportField, ReportFilter, ReportSchedule
from .permissions import (
    get_request_user_profile,
    user_is_admin,
    user_is_finance,
    user_is_manager,
)
from .report_engine import (
    list_datasources_for_role,
    rows_to_csv,
    run_report_definition,
    run_saved_report,
)
from .tenants import filter_queryset_by_organization


def _role_name(request):
    profile = get_request_user_profile(request)
    return str(getattr(profile, "role", "") or "")


def _view_mode(request):
    if user_is_admin(request) or user_is_finance(request):
        return "organization"
    if user_is_manager(request):
        return "team"
    return "self"


def _can_access_reports(request):
    return (
        user_is_admin(request)
        or user_is_finance(request)
        or user_is_manager(request)
        or bool(get_request_user_profile(request))
    )


def _can_manage_report(request, report):
    if user_is_admin(request):
        return True
    if report.owner_id == getattr(request.user, "id", None):
        return True
    if user_is_finance(request) and report.report_type in (
        Report.DATASOURCE_COMMISSIONS,
        Report.DATASOURCE_PAYOUTS,
        Report.DATASOURCE_ORDERS,
        Report.DATASOURCE_QUOTAS,
    ):
        return report.visibility != Report.VISIBILITY_PRIVATE or report.owner_id == request.user.id
    return False


def _datasource_allowed(request, datasource):
    role = _role_name(request)
    if user_is_admin(request):
        return True
    for ds in list_datasources_for_role(role):
        if ds["key"] == datasource:
            return True
    # Finance aliases
    if user_is_finance(request) and datasource in (
        Report.DATASOURCE_COMMISSIONS,
        Report.DATASOURCE_PAYOUTS,
        Report.DATASOURCE_ORDERS,
        Report.DATASOURCE_QUOTAS,
        Report.DATASOURCE_AUDIT,
        Report.DATASOURCE_PLANS,
    ):
        return True
    if user_is_manager(request) and datasource in (
        Report.DATASOURCE_COMMISSIONS,
        Report.DATASOURCE_ORDERS,
        Report.DATASOURCE_EMPLOYEES,
        Report.DATASOURCE_QUOTAS,
    ):
        return True
    return False


def _visible_reports_qs(request):
    org = getattr(request, "organization", None)
    qs = filter_queryset_by_organization(
        Report.objects.filter(is_archived=False).select_related("owner", "created_by"),
        org,
    )
    if user_is_admin(request):
        return qs
    uid = request.user.id
    role = _role_name(request)
    return qs.filter(
        Q(owner_id=uid)
        | Q(visibility=Report.VISIBILITY_ORG)
        | Q(visibility=Report.VISIBILITY_ROLE, allowed_roles__contains=[role])
    )


def _serialize_report(report, include_definition=False):
    owner = report.owner
    data = {
        "id": report.id,
        "name": report.name,
        "description": report.description,
        "report_type": report.report_type,
        "report_type_label": dict(Report.DATASOURCE_CHOICES).get(
            report.report_type, report.report_type
        ),
        "visualization": report.visualization,
        "group_by": report.group_by,
        "sort_by": report.sort_by,
        "sort_dir": report.sort_dir,
        "visibility": report.visibility,
        "allowed_roles": report.allowed_roles or [],
        "owner_id": report.owner_id,
        "owner_email": getattr(owner, "email", "") if owner else "",
        "created_by_email": getattr(report.created_by, "email", "")
        if report.created_by_id
        else "",
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        "last_run_at": report.last_run_at.isoformat() if report.last_run_at else None,
        "schedule_count": report.schedules.filter(is_active=True).count(),
    }
    if include_definition:
        data["fields"] = [
            {
                "field_key": f.field_key,
                "label": f.label,
                "display_order": f.display_order,
                "aggregation": f.aggregation,
            }
            for f in report.fields.all()
        ]
        data["filters"] = [
            {
                "field_key": f.field_key,
                "operator": f.operator,
                "value": f.value,
            }
            for f in report.filters.all()
        ]
        data["schedules"] = [
            _serialize_schedule(s) for s in report.schedules.all()[:20]
        ]
    return data


def _serialize_schedule(s):
    return {
        "id": s.id,
        "report_id": s.report_id,
        "report_name": s.report.name if s.report_id else "",
        "frequency": s.frequency,
        "delivery": s.delivery,
        "recipients": s.recipients or [],
        "is_active": s.is_active,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _next_run(frequency):
    now = timezone.now()
    if frequency == ReportSchedule.FREQ_DAILY:
        return now + timedelta(days=1)
    if frequency == ReportSchedule.FREQ_MONTHLY:
        return now + timedelta(days=30)
    return now + timedelta(days=7)


def _replace_fields(report, fields_payload):
    report.fields.all().delete()
    for idx, item in enumerate(fields_payload or []):
        key = (item.get("field_key") or item.get("key") or "").strip()
        if not key:
            continue
        ReportField.objects.create(
            report=report,
            field_key=key,
            label=(item.get("label") or "")[:128],
            display_order=item.get("display_order", idx),
            aggregation=(item.get("aggregation") or "")[:16],
        )


def _replace_filters(report, filters_payload):
    report.filters.all().delete()
    for item in filters_payload or []:
        key = (item.get("field_key") or item.get("key") or "").strip()
        if not key:
            continue
        ReportFilter.objects.create(
            report=report,
            field_key=key,
            operator=(item.get("operator") or ReportFilter.OP_EQ)[:16],
            value=item.get("value") if item.get("value") is not None else {},
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_datasources(request):
    if not _can_access_reports(request):
        raise PermissionDenied("Not allowed")
    role = _role_name(request)
    if user_is_admin(request):
        role = "Admin"
    elif user_is_finance(request):
        role = "Finance"
    elif user_is_manager(request):
        role = "Manager"
    return Response({"results": list_datasources_for_role(role)})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def analytics_report_list(request):
    if not _can_access_reports(request):
        raise PermissionDenied("Not allowed")

    if request.method == "GET":
        qs = _visible_reports_qs(request)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        rtype = (request.query_params.get("report_type") or "").strip()
        if rtype:
            qs = qs.filter(report_type=rtype)
        if (request.query_params.get("mine") or "").lower() in ("1", "true", "yes"):
            qs = qs.filter(owner_id=request.user.id)
        data = [_serialize_report(r) for r in qs[:200]]
        return Response({"count": len(data), "results": data})

    # POST create
    if not (user_is_admin(request) or user_is_finance(request) or user_is_manager(request)):
        raise PermissionDenied("Employees cannot create reports")
    payload = request.data or {}
    datasource = (payload.get("report_type") or payload.get("datasource") or "").strip()
    if not _datasource_allowed(request, datasource):
        raise PermissionDenied("Datasource not allowed for your role")
    name = (payload.get("name") or "").strip()
    if not name:
        return Response({"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST)

    org = getattr(request, "organization", None)
    report = Report.objects.create(
        organization=org,
        name=name[:200],
        description=(payload.get("description") or "")[:4000],
        report_type=datasource,
        visualization=(payload.get("visualization") or Report.VIZ_TABLE)[:16],
        group_by=(payload.get("group_by") or "")[:64],
        sort_by=(payload.get("sort_by") or "")[:64],
        sort_dir=(payload.get("sort_dir") or "desc")[:4],
        visibility=(payload.get("visibility") or Report.VISIBILITY_PRIVATE)[:16],
        allowed_roles=payload.get("allowed_roles") or [],
        owner=request.user,
        created_by=request.user,
    )
    _replace_fields(report, payload.get("fields"))
    _replace_filters(report, payload.get("filters"))
    record_audit(
        request,
        "report_created",
        {"report_id": report.id, "name": report.name, "report_type": report.report_type},
        entity_type="report",
        entity_id=str(report.id),
    )
    return Response(
        _serialize_report(report, include_definition=True),
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def analytics_report_detail(request, pk):
    report = _visible_reports_qs(request).filter(pk=pk).first()
    if not report:
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        record_audit(
            request,
            "report_viewed",
            {"report_id": report.id, "name": report.name},
            entity_type="report",
            entity_id=str(report.id),
        )
        return Response(_serialize_report(report, include_definition=True))

    if not _can_manage_report(request, report):
        raise PermissionDenied("Cannot modify this report")

    if request.method == "DELETE":
        rid, name = report.id, report.name
        report.is_archived = True
        report.save(update_fields=["is_archived", "updated_at"])
        record_audit(
            request,
            "report_deleted",
            {"report_id": rid, "name": name},
            entity_type="report",
            entity_id=str(rid),
        )
        return Response({"ok": True})

    payload = request.data or {}
    if "name" in payload and str(payload.get("name") or "").strip():
        report.name = str(payload.get("name")).strip()[:200]
    if "description" in payload:
        report.description = str(payload.get("description") or "")[:4000]
    if "visualization" in payload:
        report.visualization = str(payload.get("visualization") or Report.VIZ_TABLE)[:16]
    if "group_by" in payload:
        report.group_by = str(payload.get("group_by") or "")[:64]
    if "sort_by" in payload:
        report.sort_by = str(payload.get("sort_by") or "")[:64]
    if "sort_dir" in payload:
        report.sort_dir = str(payload.get("sort_dir") or "desc")[:4]
    if "visibility" in payload:
        report.visibility = str(payload.get("visibility") or report.visibility)[:16]
    if "allowed_roles" in payload:
        report.allowed_roles = payload.get("allowed_roles") or []
    if "report_type" in payload and _datasource_allowed(request, payload.get("report_type")):
        report.report_type = payload.get("report_type")
    report.save()
    if "fields" in payload:
        _replace_fields(report, payload.get("fields"))
    if "filters" in payload:
        _replace_filters(report, payload.get("filters"))
    record_audit(
        request,
        "report_modified",
        {"report_id": report.id, "name": report.name},
        entity_type="report",
        entity_id=str(report.id),
    )
    return Response(_serialize_report(report, include_definition=True))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def analytics_report_duplicate(request, pk):
    report = _visible_reports_qs(request).filter(pk=pk).first()
    if not report:
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)
    if not (user_is_admin(request) or user_is_finance(request) or user_is_manager(request)):
        raise PermissionDenied("Cannot duplicate")
    clone = Report.objects.create(
        organization=report.organization,
        name=f"{report.name} (Copy)"[:200],
        description=report.description,
        report_type=report.report_type,
        visualization=report.visualization,
        group_by=report.group_by,
        sort_by=report.sort_by,
        sort_dir=report.sort_dir,
        visibility=Report.VISIBILITY_PRIVATE,
        allowed_roles=[],
        owner=request.user,
        created_by=request.user,
    )
    for f in report.fields.all():
        ReportField.objects.create(
            report=clone,
            field_key=f.field_key,
            label=f.label,
            display_order=f.display_order,
            aggregation=f.aggregation,
        )
    for f in report.filters.all():
        ReportFilter.objects.create(
            report=clone,
            field_key=f.field_key,
            operator=f.operator,
            value=f.value,
        )
    record_audit(
        request,
        "report_created",
        {"report_id": clone.id, "name": clone.name, "duplicated_from": report.id},
        entity_type="report",
        entity_id=str(clone.id),
    )
    return Response(_serialize_report(clone, include_definition=True), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def analytics_report_preview(request):
    """Wizard preview — run unsaved definition."""
    if not (user_is_admin(request) or user_is_finance(request) or user_is_manager(request)):
        raise PermissionDenied("Not allowed")
    payload = request.data or {}
    datasource = (payload.get("report_type") or payload.get("datasource") or "").strip()
    if not _datasource_allowed(request, datasource):
        raise PermissionDenied("Datasource not allowed")
    profile = get_request_user_profile(request)
    try:
        result = run_report_definition(
            datasource=datasource,
            organization=getattr(request, "organization", None),
            field_keys=[
                f.get("field_key") or f.get("key")
                for f in (payload.get("fields") or [])
                if (f.get("field_key") or f.get("key"))
            ],
            filters=payload.get("filters") or [],
            group_by=payload.get("group_by") or "",
            sort_by=payload.get("sort_by") or "",
            sort_dir=payload.get("sort_dir") or "desc",
            limit=min(int(payload.get("limit") or 100), 500),
            request=request,
            profile=profile,
            view_mode=_view_mode(request),
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def analytics_report_run(request, pk):
    report = _visible_reports_qs(request).filter(pk=pk).first()
    if not report:
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)
    profile = get_request_user_profile(request)
    result = run_saved_report(
        report,
        request=request,
        profile=profile,
        view_mode=_view_mode(request),
        limit=min(int(request.data.get("limit") or request.query_params.get("limit") or 500), 2000),
    )
    report.last_run_at = timezone.now()
    report.save(update_fields=["last_run_at"])
    record_audit(
        request,
        "report_viewed",
        {"report_id": report.id, "name": report.name, "row_count": result.get("count")},
        entity_type="report",
        entity_id=str(report.id),
    )
    return Response({"report": _serialize_report(report), "result": result})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def analytics_report_export(request, pk):
    report = _visible_reports_qs(request).filter(pk=pk).first()
    if not report:
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)
    profile = get_request_user_profile(request)
    result = run_saved_report(
        report,
        request=request,
        profile=profile,
        view_mode=_view_mode(request),
        limit=5000,
    )
    report.last_run_at = timezone.now()
    report.save(update_fields=["last_run_at"])
    record_audit(
        request,
        "report_exported",
        {"report_id": report.id, "name": report.name, "format": "csv"},
        entity_type="report",
        entity_id=str(report.id),
    )
    csv_text = rows_to_csv(result)
    response = HttpResponse(csv_text, content_type="text/csv")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in report.name)[:60]
    response["Content-Disposition"] = f'attachment; filename="{safe_name or "report"}.csv"'
    return response


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def analytics_schedule_list(request):
    if not (user_is_admin(request) or user_is_finance(request) or user_is_manager(request)):
        raise PermissionDenied("Not allowed")
    org = getattr(request, "organization", None)
    if request.method == "GET":
        qs = filter_queryset_by_organization(
            ReportSchedule.objects.select_related("report").filter(is_active=True),
            org,
        )
        if not user_is_admin(request):
            qs = qs.filter(created_by=request.user)
        return Response({"results": [_serialize_schedule(s) for s in qs[:200]]})

    payload = request.data or {}
    report_id = payload.get("report_id")
    report = _visible_reports_qs(request).filter(pk=report_id).first()
    if not report:
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)
    if not _can_manage_report(request, report):
        raise PermissionDenied("Cannot schedule this report")
    freq = (payload.get("frequency") or ReportSchedule.FREQ_WEEKLY)[:16]
    schedule = ReportSchedule.objects.create(
        report=report,
        organization=org,
        frequency=freq,
        delivery=(payload.get("delivery") or ReportSchedule.DELIVERY_EMAIL_EXCEL)[:16],
        recipients=payload.get("recipients") or [getattr(request.user, "email", "")],
        is_active=True,
        next_run_at=_next_run(freq),
        created_by=request.user,
    )
    record_audit(
        request,
        "report_scheduled",
        {"report_id": report.id, "schedule_id": schedule.id, "frequency": freq},
        entity_type="report",
        entity_id=str(report.id),
    )
    return Response(_serialize_schedule(schedule), status=status.HTTP_201_CREATED)


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated])
def analytics_schedule_detail(request, pk):
    org = getattr(request, "organization", None)
    schedule = filter_queryset_by_organization(
        ReportSchedule.objects.select_related("report"), org
    ).filter(pk=pk).first()
    if not schedule:
        return Response({"error": "Schedule not found"}, status=status.HTTP_404_NOT_FOUND)
    if not _can_manage_report(request, schedule.report) and schedule.created_by_id != request.user.id:
        raise PermissionDenied("Not allowed")
    if request.method == "DELETE":
        schedule.is_active = False
        schedule.save(update_fields=["is_active", "updated_at"])
        return Response({"ok": True})
    payload = request.data or {}
    if "frequency" in payload:
        schedule.frequency = str(payload.get("frequency"))[:16]
        schedule.next_run_at = _next_run(schedule.frequency)
    if "delivery" in payload:
        schedule.delivery = str(payload.get("delivery"))[:16]
    if "recipients" in payload:
        schedule.recipients = payload.get("recipients") or []
    if "is_active" in payload:
        schedule.is_active = bool(payload.get("is_active"))
    schedule.save()
    return Response(_serialize_schedule(schedule))
