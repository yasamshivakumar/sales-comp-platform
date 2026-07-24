"""
Compensation Governance Center APIs — enterprise compliance workflow.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from .audit import record_audit
from .document_storage import open_document_file, save_document_file, validate_upload
from .models import (
    AuditLog,
    Commission,
    CommissionRule,
    CompensationDocument,
    CompensationDocumentVersion,
    CompensationPlan,
)
from .permissions import (
    get_request_user_profile,
    require_admin,
    user_is_admin,
    user_is_finance,
    user_is_manager,
)

User = get_user_model()

CATEGORY_DEFS = (
    ("compensation_plan", "Compensation Plans"),
    ("commission_policy", "Commission Policies"),
    ("quota_letter", "Quota Documents"),
    ("approval_document", "Approval Records"),
    ("employee_agreement", "Employee Agreements"),
    ("exception_approval", "Exception Approvals"),
)

LIFECYCLE_STATUSES = {
    CompensationDocument.STATUS_DRAFT,
    CompensationDocument.STATUS_PENDING_REVIEW,
    CompensationDocument.STATUS_APPROVED,
    CompensationDocument.STATUS_PUBLISHED,
    CompensationDocument.STATUS_EXPIRED,
    CompensationDocument.STATUS_ARCHIVED,
}

PUBLISHED_LIKE = (
    CompensationDocument.STATUS_PUBLISHED,
    CompensationDocument.STATUS_APPROVED,
)


def _org(request):
    org = getattr(request, "organization", None)
    if org is None:
        raise ValidationError({"error": "Organization context required."})
    return org


def _can_manage(request):
    return user_is_admin(request) or user_is_finance(request)


def _can_view(request):
    return user_is_admin(request) or user_is_finance(request) or user_is_manager(request)


def _require_view(request):
    if not _can_view(request):
        profile = get_request_user_profile(request)
        if not profile:
            raise PermissionDenied("Not allowed to view documents.")
        return "self"
    return "org"


def _require_upload(request):
    if not _can_manage(request):
        raise PermissionDenied("Only administrators and finance can upload documents.")


def _parse_date(val):
    if not val:
        return None
    if hasattr(val, "isoformat"):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def _truthy(val):
    return str(val or "").lower() in ("1", "true", "yes", "on")


def _user_label(user):
    if not user:
        return None
    return getattr(user, "email", None) or getattr(user, "username", None)


def _serialize_version(v):
    file_url = ""
    if v.storage_key:
        try:
            from django.core.files.storage import default_storage

            file_url = default_storage.url(v.storage_key)
        except Exception:
            file_url = ""
    elif v.file:
        try:
            file_url = v.file.url
        except Exception:
            file_url = ""
    return {
        "id": v.id,
        "version_number": v.version_number,
        "version_label": v.display_version,
        "status": v.status,
        "approval_status": v.approval_status,
        "effective_from": v.effective_from.isoformat() if v.effective_from else None,
        "effective_to": v.effective_to.isoformat() if v.effective_to else None,
        "description": v.description or "",
        "file_name": v.file_name,
        "file_size": v.file_size,
        "content_type": v.content_type,
        "storage_backend": v.storage_backend,
        "file_url": file_url,
        "has_file": bool(v.storage_key or (v.file and v.file.name)),
        "uploaded_by": _user_label(v.uploaded_by),
        "approver": _user_label(v.approver) if v.approver_id else None,
        "approver_id": v.approver_id,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _linked_rules_payload(doc):
    return [
        {
            "id": r.id,
            "name": r.name,
            "rule_type": r.rule_type,
            "plan_id": r.compensation_plan_id,
            "is_active": r.is_active,
        }
        for r in doc.linked_rules.all()[:50]
    ]


def _relationships_payload(doc, org):
    calc_qs = Commission.objects.filter(
        organization=org, supporting_document_id=doc.id
    ).order_by("-id")[:25]
    calculations = [
        {
            "id": c.id,
            "status": c.status,
            "amount": str(c.commission_amount or ""),
            "sale_id": c.sale_id,
            "employee": getattr(c.employee, "email", None)
            or getattr(c.employee, "name", None)
            or str(c.employee_id),
        }
        for c in calc_qs.select_related("employee")
    ]
    audit_rows = AuditLog.objects.filter(
        organization=org,
        module="documents",
        entity_id=str(doc.id),
    ).order_by("-created_at")[:40]
    audit_history = [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "action": row.action,
            "action_label": (row.action or "").replace("document_", "").replace("_", " ").title(),
            "user_email": row.user_email or "",
            "reason": row.reason or (row.detail or {}).get("reason") or "",
            "detail": row.detail or {},
        }
        for row in audit_rows
    ]
    return {
        "linked_plans": (
            [{"id": doc.related_plan_id, "name": doc.related_plan.plan_name}]
            if doc.related_plan_id
            else []
        ),
        "linked_rules": _linked_rules_payload(doc),
        "commission_calculations": calculations,
        "calculation_count": Commission.objects.filter(
            organization=org, supporting_document_id=doc.id
        ).count(),
        "audit_history": audit_history,
    }


def _serialize_document(doc, include_versions=False, include_relations=False, org=None):
    cv = doc.current_version
    created_by = doc.created_by or doc.uploaded_by
    payload = {
        "id": doc.id,
        "name": doc.name,
        "document_type": doc.document_type,
        "document_type_label": doc.get_document_type_display(),
        "category": doc.get_document_type_display(),
        "status": doc.status,
        "status_label": doc.get_status_display(),
        "lifecycle_status": doc.status,
        "business_unit": doc.business_unit or "",
        "related_plan_id": doc.related_plan_id,
        "related_plan_name": doc.related_plan.plan_name if doc.related_plan_id else None,
        "linked_plan": doc.related_plan.plan_name if doc.related_plan_id else None,
        "linked_rules": _linked_rules_payload(doc),
        "linked_rule_ids": list(doc.linked_rules.values_list("id", flat=True)),
        "linked_rule_names": ", ".join(doc.linked_rules.values_list("name", flat=True)[:5]) or "—",
        "approval_required": doc.approval_required,
        "approval_status": doc.approval_status,
        "approval_status_label": doc.get_approval_status_display(),
        "description": doc.description or "",
        "created_by": _user_label(created_by),
        "reviewed_by": _user_label(doc.reviewed_by),
        "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
        "approved_by": _user_label(doc.approved_by),
        "approved_at": doc.approved_at.isoformat() if doc.approved_at else None,
        "uploaded_by": _user_label(doc.uploaded_by),
        "owner": _user_label(created_by),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "last_activity_at": (
            doc.last_activity_at.isoformat()
            if doc.last_activity_at
            else (doc.updated_at.isoformat() if doc.updated_at else None)
        ),
        "current_version": _serialize_version(cv) if cv else None,
        "version": cv.display_version if cv else None,
        "effective_from": cv.effective_from.isoformat() if cv and cv.effective_from else None,
        "effective_to": cv.effective_to.isoformat() if cv and cv.effective_to else None,
        "content_type": cv.content_type if cv else None,
        "file_name": cv.file_name if cv else None,
        "year": (cv.effective_from.year if cv and cv.effective_from else doc.created_at.year),
        "governance_refs": {
            "document_id": doc.id,
            "version_id": cv.id if cv else None,
            "version_label": cv.display_version if cv else None,
            "plan_id": doc.related_plan_id,
            "approval_status": doc.approval_status,
            "lifecycle_status": doc.status,
            "approved_by": _user_label(doc.approved_by),
            "approved_at": doc.approved_at.isoformat() if doc.approved_at else None,
        },
    }
    if include_versions:
        payload["versions"] = [
            _serialize_version(v) for v in doc.versions.all().order_by("-version_number")
        ]
    if include_relations and org is not None:
        payload["relationships"] = _relationships_payload(doc, org)
    return payload


def _scoped_queryset(request, scope):
    org = _org(request)
    qs = CompensationDocument.objects.filter(organization=org).select_related(
        "related_plan",
        "current_version",
        "uploaded_by",
        "created_by",
        "reviewed_by",
        "approved_by",
        "current_version__uploaded_by",
        "current_version__approver",
    ).prefetch_related("linked_rules")
    if scope == "self":
        profile = get_request_user_profile(request)
        plan_id = getattr(profile, "assigned_compensation_plan_id", None) if profile else None
        if not plan_id:
            return qs.none()
        qs = qs.filter(related_plan_id=plan_id, status__in=PUBLISHED_LIKE)
    return qs


def _resolve_approver(org, approver_id=None, approver_email=None):
    email = (approver_email or "").strip().lower()
    if email:
        return User.objects.filter(email__iexact=email).first()
    if not approver_id:
        return None
    try:
        uid = int(approver_id)
    except (TypeError, ValueError):
        return None
    return User.objects.filter(pk=uid).first()


def _initial_status(approval_required, publish, as_template):
    if as_template or not publish:
        return CompensationDocument.STATUS_DRAFT
    if approval_required:
        return CompensationDocument.STATUS_PENDING_REVIEW
    return CompensationDocument.STATUS_PUBLISHED


def _set_linked_rules(doc, org, raw_ids):
    if raw_ids is None:
        return
    if isinstance(raw_ids, str):
        raw_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
    ids = []
    for item in raw_ids or []:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    rules = CommissionRule.objects.filter(organization=org, id__in=ids)
    doc.linked_rules.set(rules)


def _build_alerts(qs, org, pending_n, expiring_n):
    alerts = []
    if expiring_n:
        alerts.append(
            {
                "severity": "warning",
                "code": "expiring_documents",
                "message": f"{expiring_n} document{'s' if expiring_n != 1 else ''} expire within 30 days",
            }
        )
    if pending_n:
        alerts.append(
            {
                "severity": "warning",
                "code": "pending_approval",
                "message": f"{pending_n} polic{'ies' if pending_n != 1 else 'y'} waiting for approval",
            }
        )
    plans = CompensationPlan.objects.filter(organization=org)
    missing = 0
    for plan in plans[:200]:
        has_evidence = qs.filter(
            related_plan_id=plan.id,
            status__in=PUBLISHED_LIKE,
        ).exists()
        if not has_evidence:
            missing += 1
    if missing:
        alerts.append(
            {
                "severity": "critical",
                "code": "missing_evidence",
                "message": f"{missing} compensation plan{'s' if missing != 1 else ''} missing approved documents",
            }
        )
    return alerts, missing


def _governance_score(total, approved_n, pending_n, expiring_n, missing_n):
    if total <= 0 and missing_n <= 0:
        return 100
    denom = max(total, 1)
    approved_ratio = approved_n / denom
    pending_penalty = min(pending_n / denom, 1.0)
    expiring_penalty = min(expiring_n / denom, 1.0)
    missing_penalty = min(missing_n / max(missing_n + approved_n, 1), 1.0)
    score = (
        approved_ratio * 45
        + (1 - pending_penalty) * 20
        + (1 - expiring_penalty) * 15
        + (1 - missing_penalty) * 20
    )
    return max(0, min(100, round(score)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_summary(request):
    scope = _require_view(request)
    org = _org(request)
    qs = _scoped_queryset(request, scope)
    today = date.today()
    soon = today + timedelta(days=30)

    for doc in qs.filter(
        status__in=PUBLISHED_LIKE,
        current_version__effective_to__lt=today,
    )[:50]:
        doc.refresh_lifecycle(save=True)

    qs = _scoped_queryset(request, scope)
    published = qs.filter(status__in=PUBLISHED_LIKE)
    pending = qs.filter(
        Q(status=CompensationDocument.STATUS_PENDING_REVIEW)
        | Q(approval_status__in=(
            CompensationDocument.APPROVAL_PENDING,
            CompensationDocument.APPROVAL_IN_REVIEW,
        ))
    ).distinct()
    expiring = published.filter(
        current_version__effective_to__isnull=False,
        current_version__effective_to__gte=today,
        current_version__effective_to__lte=soon,
    )
    approved_docs = qs.filter(
        Q(status__in=PUBLISHED_LIKE) | Q(approval_status=CompensationDocument.APPROVAL_APPROVED)
    ).distinct()

    alerts, missing_evidence = _build_alerts(qs, org, pending.count(), expiring.count())
    total = qs.count()
    score = _governance_score(
        total, approved_docs.count(), pending.count(), expiring.count(), missing_evidence
    )

    storage_bytes = (
        CompensationDocumentVersion.objects.filter(document__in=qs).aggregate(total=Sum("file_size"))[
            "total"
        ]
        or 0
    )
    by_type = {
        row["document_type"]: row["c"]
        for row in qs.values("document_type").annotate(c=Count("id"))
    }
    categories = [
        {"key": key, "label": label, "count": by_type.get(key, 0)} for key, label in CATEGORY_DEFS
    ]

    activity_rows = AuditLog.objects.filter(organization=org, module="documents").order_by(
        "-created_at"
    )[:15]
    recent_activity = [
        {
            "id": row.id,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "action": row.action,
            "action_label": (row.action or "").replace("document_", "").replace("_", " ").title(),
            "user_email": row.user_email or "",
            "document_name": (row.detail or {}).get("name") or (row.detail or {}).get("file") or "",
            "reason": row.reason or (row.detail or {}).get("reason") or "",
            "detail": row.detail or {},
        }
        for row in activity_rows
    ]

    return Response(
        {
            "total": total,
            "governance_score": score,
            "approved_documents": approved_docs.count(),
            "active": published.count(),
            "active_policies": published.count(),
            "published": published.count(),
            "pending_approval": pending.count(),
            "expiring": expiring.count(),
            "expiring_soon": expiring.count(),
            "missing_evidence": missing_evidence,
            "archived": qs.filter(status=CompensationDocument.STATUS_ARCHIVED).count(),
            "expired": qs.filter(status=CompensationDocument.STATUS_EXPIRED).count(),
            "draft": qs.filter(status=CompensationDocument.STATUS_DRAFT).count(),
            "storage_bytes": storage_bytes,
            "storage_mb": round(storage_bytes / (1024 * 1024), 2),
            "categories": categories,
            "alerts": alerts,
            "recent_activity": recent_activity,
            "recently_added": qs.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def document_list_create(request):
    if request.method == "GET":
        scope = _require_view(request)
        qs = _scoped_queryset(request, scope)
        doc_type = (request.query_params.get("document_type") or "").strip()
        status_f = (request.query_params.get("status") or "").strip()
        if status_f == "active":
            status_f = CompensationDocument.STATUS_PUBLISHED
        plan_id = request.query_params.get("related_plan")
        year = request.query_params.get("year")
        q = (request.query_params.get("q") or "").strip()
        if doc_type:
            qs = qs.filter(document_type=doc_type)
        if status_f:
            qs = qs.filter(status=status_f)
        if plan_id:
            qs = qs.filter(related_plan_id=plan_id)
        if year:
            try:
                y = int(year)
                qs = qs.filter(
                    Q(current_version__effective_from__year=y) | Q(created_at__year=y)
                )
            except (TypeError, ValueError):
                pass
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(business_unit__icontains=q)
                | Q(current_version__file_name__icontains=q)
            )
        results = [_serialize_document(d) for d in qs[:200]]
        return Response({"results": results, "count": len(results)})

    _require_upload(request)
    org = _org(request)
    name = (request.data.get("name") or "").strip()
    document_type = (request.data.get("document_type") or CompensationDocument.TYPE_OTHER).strip()
    if not name:
        raise ValidationError({"name": "Document name is required."})
    valid_types = {c[0] for c in CompensationDocument.TYPE_CHOICES}
    if document_type not in valid_types:
        raise ValidationError({"document_type": "Invalid document type."})

    as_template = _truthy(request.data.get("as_template"))
    publish = _truthy(request.data.get("publish")) if "publish" in request.data else True
    uploaded = request.FILES.get("file")
    if uploaded:
        try:
            validate_upload(uploaded)
        except ValueError as exc:
            raise ValidationError({"file": str(exc)}) from exc
    elif not as_template:
        raise ValidationError({"file": "Upload a PDF, DOCX, XLSX, or CSV file."})

    related_plan = None
    plan_id = request.data.get("related_plan") or request.data.get("related_plan_id")
    if plan_id:
        related_plan = CompensationPlan.objects.filter(id=plan_id, organization=org).first()
        if related_plan is None:
            raise ValidationError({"related_plan": "Plan not found in this organization."})

    approval_required = (
        _truthy(request.data.get("approval_required"))
        if "approval_required" in request.data
        else True
    )
    description = (request.data.get("description") or "").strip()
    business_unit = (request.data.get("business_unit") or "").strip()[:128]
    version_label = (
        request.data.get("version_number") or request.data.get("version_label") or "v1"
    ).strip()
    effective_from = request.data.get("effective_start_date") or request.data.get("effective_from")
    effective_to = request.data.get("effective_end_date") or request.data.get("effective_to")
    approver = _resolve_approver(
        org,
        request.data.get("approver") or request.data.get("approver_id"),
        request.data.get("approver_email"),
    )
    initial_status = _initial_status(approval_required, publish and not as_template, as_template)
    doc_approval = CompensationDocument.APPROVAL_NOT_STARTED
    if initial_status == CompensationDocument.STATUS_PENDING_REVIEW:
        doc_approval = CompensationDocument.APPROVAL_PENDING
    elif initial_status == CompensationDocument.STATUS_PUBLISHED:
        doc_approval = CompensationDocument.APPROVAL_APPROVED

    with transaction.atomic():
        doc = CompensationDocument.objects.create(
            organization=org,
            name=name[:255],
            document_type=document_type,
            related_plan=related_plan,
            business_unit=business_unit,
            status=initial_status,
            approval_required=approval_required,
            approval_status=doc_approval,
            description=description,
            created_by=request.user,
            uploaded_by=request.user,
            approved_by=request.user if doc_approval == CompensationDocument.APPROVAL_APPROVED else None,
            approved_at=timezone.now()
            if doc_approval == CompensationDocument.APPROVAL_APPROVED
            else None,
            last_activity_at=timezone.now(),
        )
        _set_linked_rules(
            doc,
            org,
            request.data.get("linked_rules") or request.data.get("linked_rule_ids"),
        )
        if uploaded:
            meta = save_document_file(org.id, doc.id, 1, uploaded)
        else:
            meta = {
                "storage_backend": "local",
                "storage_key": "",
                "file_name": "",
                "content_type": "",
                "file_size": 0,
            }
        ver_approval = (
            CompensationDocumentVersion.APPROVAL_PENDING
            if approval_required
            else CompensationDocumentVersion.APPROVAL_NOT_REQUIRED
        )
        if doc_approval == CompensationDocument.APPROVAL_APPROVED:
            ver_approval = CompensationDocumentVersion.APPROVAL_APPROVED
        ver = CompensationDocumentVersion.objects.create(
            document=doc,
            version_number=1,
            version_label=version_label[:32] or "v1",
            storage_backend=meta["storage_backend"],
            storage_key=meta["storage_key"],
            file_name=meta["file_name"],
            content_type=meta["content_type"],
            file_size=meta["file_size"],
            effective_from=_parse_date(effective_from),
            effective_to=_parse_date(effective_to),
            description=description,
            status=CompensationDocumentVersion.STATUS_ACTIVE,
            approval_status=ver_approval,
            approver=approver,
            uploaded_by=request.user,
        )
        if meta["storage_key"]:
            ver.file.name = meta["storage_key"]
            ver.save(update_fields=["file"])
        doc.current_version = ver
        doc.save(update_fields=["current_version", "updated_at"])
        doc.refresh_lifecycle(save=True)

    record_audit(
        request,
        "document_uploaded",
        {
            "document_id": doc.id,
            "name": doc.name,
            "file": ver.file_name,
            "version": ver.display_version,
            "status": doc.status,
            "as_template": as_template,
            "reason": description
            or ("Document template created" if as_template else "New compensation document"),
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org),
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def document_detail(request, pk):
    scope = _require_view(request)
    org = _org(request)
    doc = _scoped_queryset(request, scope).filter(pk=pk).first()
    if not doc:
        raise NotFound("Document not found.")

    if request.method == "GET":
        record_audit(
            request,
            "document_viewed",
            {"document_id": doc.id, "name": doc.name},
            module="documents",
            entity_type="compensation_document",
            entity_id=str(doc.id),
        )
        doc.touch_activity(save=True)
        return Response(
            _serialize_document(doc, include_versions=True, include_relations=True, org=org)
        )

    if request.method == "DELETE":
        require_admin(request)
        doc_id = doc.id
        name = doc.name
        doc.delete()
        record_audit(
            request,
            "document_deleted",
            {"document_id": doc_id, "name": name},
            module="documents",
            entity_type="compensation_document",
            entity_id=str(doc_id),
        )
        return Response({"ok": True})

    if not _can_manage(request):
        raise PermissionDenied("Not allowed to update documents.")
    payload = request.data or {}
    if "status" in payload:
        st = str(payload.get("status") or "").strip()
        if st == "active":
            st = CompensationDocument.STATUS_PUBLISHED
        if st in LIFECYCLE_STATUSES:
            doc.status = st
    if "name" in payload and str(payload.get("name") or "").strip():
        doc.name = str(payload.get("name")).strip()[:255]
    if "description" in payload:
        doc.description = str(payload.get("description") or "")
    if "business_unit" in payload:
        doc.business_unit = str(payload.get("business_unit") or "")[:128]
    if "approval_required" in payload:
        doc.approval_required = _truthy(payload.get("approval_required"))
    if "related_plan" in payload or "related_plan_id" in payload:
        plan_id = payload.get("related_plan") or payload.get("related_plan_id")
        if plan_id:
            plan = CompensationPlan.objects.filter(id=plan_id, organization=org).first()
            if not plan:
                raise ValidationError({"related_plan": "Plan not found."})
            doc.related_plan = plan
        else:
            doc.related_plan = None
    doc.last_activity_at = timezone.now()
    doc.save()
    if "linked_rules" in payload or "linked_rule_ids" in payload:
        _set_linked_rules(
            doc, org, payload.get("linked_rules") or payload.get("linked_rule_ids")
        )
    if payload.get("status") == CompensationDocument.STATUS_ARCHIVED:
        record_audit(
            request,
            "document_archived",
            {"document_id": doc.id, "name": doc.name},
            module="documents",
            entity_type="compensation_document",
            entity_id=str(doc.id),
        )
    else:
        record_audit(
            request,
            "document_updated",
            {"document_id": doc.id, "name": doc.name, "status": doc.status},
            module="documents",
            entity_type="compensation_document",
            entity_id=str(doc.id),
        )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org)
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def document_new_version(request, pk):
    _require_upload(request)
    org = _org(request)
    doc = CompensationDocument.objects.filter(organization=org, pk=pk).first()
    if not doc:
        raise NotFound("Document not found.")
    uploaded = request.FILES.get("file")
    try:
        validate_upload(uploaded)
    except ValueError as exc:
        raise ValidationError({"file": str(exc)}) from exc

    last = doc.versions.order_by("-version_number").first()
    next_n = (last.version_number + 1) if last else 1
    version_label = (
        request.data.get("version_number")
        or request.data.get("version_label")
        or f"v{next_n}"
    ).strip()
    approver = _resolve_approver(
        org,
        request.data.get("approver") or request.data.get("approver_id"),
        request.data.get("approver_email"),
    )
    approval_required = doc.approval_required or _truthy(request.data.get("approval_required"))

    with transaction.atomic():
        if doc.current_version_id:
            CompensationDocumentVersion.objects.filter(pk=doc.current_version_id).update(
                status=CompensationDocumentVersion.STATUS_ARCHIVED
            )
        meta = save_document_file(org.id, doc.id, next_n, uploaded)
        ver = CompensationDocumentVersion.objects.create(
            document=doc,
            version_number=next_n,
            version_label=version_label[:32],
            storage_backend=meta["storage_backend"],
            storage_key=meta["storage_key"],
            file_name=meta["file_name"],
            content_type=meta["content_type"],
            file_size=meta["file_size"],
            effective_from=_parse_date(
                request.data.get("effective_start_date") or request.data.get("effective_from")
            ),
            effective_to=_parse_date(
                request.data.get("effective_end_date") or request.data.get("effective_to")
            ),
            description=(request.data.get("description") or "").strip(),
            status=CompensationDocumentVersion.STATUS_ACTIVE,
            approval_status=(
                CompensationDocumentVersion.APPROVAL_PENDING
                if approval_required
                else CompensationDocumentVersion.APPROVAL_NOT_REQUIRED
            ),
            approver=approver,
            uploaded_by=request.user,
        )
        if meta["storage_key"]:
            ver.file.name = meta["storage_key"]
            ver.save(update_fields=["file"])
        old_label = last.display_version if last else None
        doc.current_version = ver
        doc.approval_required = approval_required
        if approval_required:
            doc.status = CompensationDocument.STATUS_PENDING_REVIEW
            doc.approval_status = CompensationDocument.APPROVAL_PENDING
            doc.approved_by = None
            doc.approved_at = None
        else:
            doc.status = CompensationDocument.STATUS_PUBLISHED
            doc.approval_status = CompensationDocument.APPROVAL_APPROVED
        doc.last_activity_at = timezone.now()
        doc.save()

    record_audit(
        request,
        "document_version_updated",
        {
            "document_id": doc.id,
            "name": doc.name,
            "old_version": old_label,
            "new_version": ver.display_version,
            "file": ver.file_name,
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org),
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_review(request, pk):
    if not _can_manage(request):
        raise PermissionDenied("Only administrators and finance can review documents.")
    org = _org(request)
    doc = CompensationDocument.objects.filter(organization=org, pk=pk).first()
    if not doc:
        raise NotFound("Document not found.")
    reason = (request.data.get("reason") or "").strip()
    doc.reviewed_by = request.user
    doc.reviewed_at = timezone.now()
    doc.approval_status = CompensationDocument.APPROVAL_IN_REVIEW
    doc.status = CompensationDocument.STATUS_PENDING_REVIEW
    doc.last_activity_at = timezone.now()
    doc.save()
    record_audit(
        request,
        "document_reviewed",
        {
            "document_id": doc.id,
            "name": doc.name,
            "reason": reason or "Document marked as reviewed",
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org)
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_approve(request, pk):
    if not _can_manage(request):
        raise PermissionDenied("Only administrators and finance can approve documents.")
    org = _org(request)
    doc = CompensationDocument.objects.filter(organization=org, pk=pk).select_related(
        "current_version"
    ).first()
    if not doc:
        raise NotFound("Document not found.")
    cv = doc.current_version
    if not cv:
        raise ValidationError({"error": "Document has no version to approve."})
    reason = (request.data.get("reason") or "").strip()
    publish = _truthy(request.data.get("publish")) if "publish" in request.data else True
    with transaction.atomic():
        cv.approval_status = CompensationDocumentVersion.APPROVAL_APPROVED
        if not cv.approver_id:
            cv.approver = request.user
        cv.save(update_fields=["approval_status", "approver"])
        if not doc.reviewed_by_id:
            doc.reviewed_by = request.user
            doc.reviewed_at = timezone.now()
        doc.approved_by = request.user
        doc.approved_at = timezone.now()
        doc.approval_status = CompensationDocument.APPROVAL_APPROVED
        today = date.today()
        if publish and (not cv.effective_from or cv.effective_from <= today):
            doc.status = CompensationDocument.STATUS_PUBLISHED
        else:
            doc.status = CompensationDocument.STATUS_APPROVED
        doc.last_activity_at = timezone.now()
        doc.save()

    record_audit(
        request,
        "document_approved",
        {
            "document_id": doc.id,
            "name": doc.name,
            "version": cv.display_version,
            "status": doc.status,
            "reason": reason or "Document approved",
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org)
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_publish(request, pk):
    if not _can_manage(request):
        raise PermissionDenied("Only administrators and finance can publish documents.")
    org = _org(request)
    doc = CompensationDocument.objects.filter(organization=org, pk=pk).select_related(
        "current_version"
    ).first()
    if not doc:
        raise NotFound("Document not found.")
    if doc.approval_required and doc.approval_status != CompensationDocument.APPROVAL_APPROVED:
        raise ValidationError({"error": "Document must be approved before publish."})
    doc.status = CompensationDocument.STATUS_PUBLISHED
    doc.last_activity_at = timezone.now()
    doc.save(update_fields=["status", "last_activity_at", "updated_at"])
    record_audit(
        request,
        "document_published",
        {
            "document_id": doc.id,
            "name": doc.name,
            "version": doc.current_version.display_version if doc.current_version else None,
            "reason": (request.data.get("reason") or "Document published for calculations"),
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org)
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_restore_version(request, pk, version_id):
    _require_upload(request)
    org = _org(request)
    doc = CompensationDocument.objects.filter(organization=org, pk=pk).first()
    if not doc:
        raise NotFound("Document not found.")
    ver = doc.versions.filter(pk=version_id).first()
    if not ver:
        raise NotFound("Version not found.")
    with transaction.atomic():
        doc.versions.exclude(pk=ver.pk).update(status=CompensationDocumentVersion.STATUS_ARCHIVED)
        ver.status = CompensationDocumentVersion.STATUS_ACTIVE
        ver.save(update_fields=["status"])
        doc.current_version = ver
        if ver.approval_status == CompensationDocumentVersion.APPROVAL_PENDING:
            doc.status = CompensationDocument.STATUS_PENDING_REVIEW
            doc.approval_status = CompensationDocument.APPROVAL_PENDING
        elif ver.approval_status == CompensationDocumentVersion.APPROVAL_APPROVED:
            doc.status = CompensationDocument.STATUS_PUBLISHED
            doc.approval_status = CompensationDocument.APPROVAL_APPROVED
        else:
            doc.status = CompensationDocument.STATUS_PUBLISHED
        doc.last_activity_at = timezone.now()
        doc.save()

    record_audit(
        request,
        "document_version_restored",
        {
            "document_id": doc.id,
            "name": doc.name,
            "version": ver.display_version,
            "reason": (request.data.get("reason") or "Version restored as current"),
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    return Response(
        _serialize_document(doc, include_versions=True, include_relations=True, org=org)
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_download(request, pk, version_id=None):
    scope = _require_view(request)
    doc = _scoped_queryset(request, scope).filter(pk=pk).first()
    if not doc:
        raise NotFound("Document not found.")
    if version_id:
        ver = doc.versions.filter(pk=version_id).first()
    else:
        ver = doc.current_version
    if not ver:
        raise NotFound("Version not found.")
    try:
        handle, filename, content_type = open_document_file(ver)
    except FileNotFoundError as exc:
        raise NotFound(str(exc)) from exc

    reason = (request.query_params.get("reason") or "").strip()
    inline = _truthy(request.query_params.get("inline"))
    record_audit(
        request,
        "document_downloaded" if not inline else "document_viewed",
        {
            "document_id": doc.id,
            "name": doc.name,
            "file": filename,
            "version": ver.display_version,
            "reason": reason or ("Document preview" if inline else "Document download"),
            "inline": inline,
        },
        module="documents",
        entity_type="compensation_document",
        entity_id=str(doc.id),
    )
    doc.touch_activity(save=True)
    resp = FileResponse(handle, content_type=content_type)
    disposition = "inline" if inline else "attachment"
    resp["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return resp


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def plan_documents(request, plan_id):
    scope = _require_view(request)
    org = _org(request)
    plan = CompensationPlan.objects.filter(id=plan_id, organization=org).first()
    if not plan:
        raise NotFound("Plan not found.")
    qs = _scoped_queryset(request, scope).filter(related_plan_id=plan_id)
    return Response({"results": [_serialize_document(d) for d in qs]})


def resolve_supporting_document_for_plan(plan, organization=None):
    """Pick the latest published/approved document for commission calculation evidence."""
    if plan is None:
        return None, None
    qs = CompensationDocument.objects.filter(
        related_plan=plan,
        status__in=PUBLISHED_LIKE,
        current_version__isnull=False,
    )
    if organization is not None:
        qs = qs.filter(organization=organization)
    doc = qs.order_by("-updated_at").first()
    if not doc:
        return None, None
    return doc, doc.current_version
