"""APIs for employee compensation overrides and the compensation hierarchy."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import record_audit
from .compensation_overrides import (
    active_overrides_for_employee,
    diff_snapshots,
    event_payload,
    override_payload,
    plan_rules_for_display,
    record_override_event,
    snapshot,
)
from .models import (
    CompensationPlan,
    EmployeeCompensationOverride,
    EmployeeCompensationOverrideEvent,
    UserProfile,
)
from .permissions import user_is_admin
from .tenants import filter_queryset_by_organization

User = get_user_model()

EDITABLE_FIELDS = {
    "name",
    "override_type",
    "value",
    "value_unit",
    "previous_value",
    "effective_from",
    "effective_to",
    "reason",
    "priority",
    "stop_on_match",
    "approval_required",
}


def _require_admin(request):
    if not user_is_admin(request):
        raise PermissionDenied(
            "Only administrators can manage employee compensation overrides"
        )


def _org(request):
    return getattr(request, "organization", None)


def _parse_date(value, field, required=False):
    if value in (None, ""):
        if required:
            raise ValidationError({field: "This field is required."})
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValidationError({field: "Use the YYYY-MM-DD format."})


def _parse_decimal(value, field, required=False):
    if value in (None, ""):
        if required:
            raise ValidationError({field: "This field is required."})
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: "Enter a number."})


def _override_queryset(request):
    qs = EmployeeCompensationOverride.objects.select_related(
        "employee", "compensation_plan", "approver", "approved_by", "created_by"
    )
    return filter_queryset_by_organization(qs, _org(request))


def _resolve_employee(request, employee_id):
    if not employee_id:
        raise ValidationError({"employee": "Select an employee."})
    qs = filter_queryset_by_organization(UserProfile.objects.all(), _org(request))
    profile = qs.filter(pk=employee_id).first()
    if profile is None:
        raise ValidationError({"employee": "Employee not found in this organization."})
    return profile


def _resolve_plan(request, plan_id, profile):
    if not plan_id:
        return getattr(profile, "assigned_compensation_plan", None)
    qs = filter_queryset_by_organization(CompensationPlan.objects.all(), _org(request))
    plan = qs.filter(pk=plan_id).first()
    if plan is None:
        raise ValidationError({"compensation_plan": "Plan not found."})
    return plan


def _resolve_user(request, user_id, field):
    if not user_id:
        return None
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise ValidationError({field: "User not found."})
    return user


def _validate_window(effective_from, effective_to):
    if effective_from and effective_to and effective_to < effective_from:
        raise ValidationError(
            {"effective_to": "Effective To must be on or after Effective From."}
        )


def _conflicting_overrides(profile, override_type, effective_from, effective_to, exclude_pk=None):
    """Approved overrides of the same type whose window collides."""
    qs = EmployeeCompensationOverride.objects.filter(
        employee=profile,
        override_type=override_type,
        status__in=[
            EmployeeCompensationOverride.STATUS_APPROVED,
            EmployeeCompensationOverride.STATUS_PENDING,
        ],
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    qs = qs.filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
    )
    if effective_to:
        qs = qs.filter(effective_from__lte=effective_to)
    return qs


# ---------------------------------------------------------------------------
# List / create
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def compensation_overrides(request):
    _require_admin(request)

    if request.method == "GET":
        qs = _override_queryset(request)
        params = request.query_params
        if params.get("employee"):
            qs = qs.filter(employee_id=params["employee"])
        if params.get("plan"):
            qs = qs.filter(compensation_plan_id=params["plan"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("override_type"):
            qs = qs.filter(override_type=params["override_type"])
        if params.get("active_only") in ("1", "true", "True"):
            today = timezone.localdate()
            qs = qs.filter(
                status=EmployeeCompensationOverride.STATUS_APPROVED,
                effective_from__lte=today,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(employee__name__icontains=q)
                | Q(employee__employee_id__icontains=q)
            )
        return Response({"results": [override_payload(row) for row in qs]})

    data = request.data or {}
    profile = _resolve_employee(request, data.get("employee"))
    plan = _resolve_plan(request, data.get("compensation_plan"), profile)
    override_type = data.get("override_type") or EmployeeCompensationOverride.TYPE_COMMISSION_RATE
    valid_types = dict(EmployeeCompensationOverride.TYPE_CHOICES)
    if override_type not in valid_types:
        raise ValidationError({"override_type": "Unknown override type."})

    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError({"name": "Give the override a name."})

    effective_from = _parse_date(data.get("effective_from"), "effective_from", required=True)
    effective_to = _parse_date(data.get("effective_to"), "effective_to")
    _validate_window(effective_from, effective_to)

    conflicts = _conflicting_overrides(profile, override_type, effective_from, effective_to)
    if conflicts.exists():
        raise ValidationError(
            {
                "effective_from": (
                    f"{profile.name or profile.email} already has a "
                    f"{valid_types[override_type]} override covering these dates "
                    f"({conflicts.first().name})."
                )
            }
        )

    approval_required = bool(data.get("approval_required", True))
    override = EmployeeCompensationOverride.objects.create(
        organization=_org(request),
        employee=profile,
        compensation_plan=plan,
        name=name,
        override_type=override_type,
        value=_parse_decimal(data.get("value"), "value"),
        value_unit=(
            data.get("value_unit")
            or EmployeeCompensationOverride.DEFAULT_UNIT_FOR_TYPE.get(
                override_type, EmployeeCompensationOverride.UNIT_PERCENT
            )
        ),
        previous_value=_parse_decimal(data.get("previous_value"), "previous_value"),
        effective_from=effective_from,
        effective_to=effective_to,
        reason=(data.get("reason") or "").strip(),
        priority=int(data.get("priority") or 1),
        stop_on_match=bool(data.get("stop_on_match", True)),
        approval_required=approval_required,
        approver=_resolve_user(request, data.get("approver"), "approver"),
        status=(
            EmployeeCompensationOverride.STATUS_DRAFT
            if approval_required
            else EmployeeCompensationOverride.STATUS_APPROVED
        ),
        created_by=request.user if request.user.is_authenticated else None,
    )
    if not approval_required:
        override.approved_by = request.user if request.user.is_authenticated else None
        override.approved_at = timezone.now()
        override.save(update_fields=["approved_by", "approved_at"])

    record_override_event(
        override,
        EmployeeCompensationOverrideEvent.EVENT_CREATED,
        actor=request.user,
        reason=override.reason,
        new_value=snapshot(override),
    )
    _audit(request, "compensation_override_created", override)
    return Response(override_payload(override, include_history=True), status=201)


# ---------------------------------------------------------------------------
# Detail / update / delete
# ---------------------------------------------------------------------------


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def compensation_override_detail(request, pk):
    _require_admin(request)
    override = get_object_or_404(_override_queryset(request), pk=pk)

    if request.method == "GET":
        return Response(override_payload(override, include_history=True))

    if request.method == "DELETE":
        before = snapshot(override)
        reason = (request.query_params.get("reason") or "").strip()
        override.status = EmployeeCompensationOverride.STATUS_REVOKED
        override.save(update_fields=["status", "updated_at"])
        record_override_event(
            override,
            EmployeeCompensationOverrideEvent.EVENT_REMOVED,
            actor=request.user,
            reason=reason or "Override removed",
            old_value=before,
            new_value=snapshot(override),
            changed_fields=["status"],
        )
        _audit(request, "compensation_override_removed", override, reason=reason)
        return Response({"status": "removed", "override": override_payload(override)})

    data = request.data or {}
    before = snapshot(override)

    if "employee" in data:
        override.employee = _resolve_employee(request, data.get("employee"))
    if "compensation_plan" in data:
        override.compensation_plan = _resolve_plan(
            request, data.get("compensation_plan"), override.employee
        )
    if "approver" in data:
        override.approver = _resolve_user(request, data.get("approver"), "approver")

    for field in EDITABLE_FIELDS:
        if field not in data:
            continue
        if field in ("effective_from", "effective_to"):
            setattr(override, field, _parse_date(data[field], field))
        elif field in ("value", "previous_value"):
            setattr(override, field, _parse_decimal(data[field], field))
        elif field in ("stop_on_match", "approval_required"):
            setattr(override, field, bool(data[field]))
        elif field == "priority":
            override.priority = int(data[field] or 1)
        else:
            setattr(override, field, data[field])

    if override.effective_from is None:
        raise ValidationError({"effective_from": "This field is required."})
    _validate_window(override.effective_from, override.effective_to)

    # Editing an approved override sends it back for re-approval so the
    # audit trail always shows who signed off on the values that ran.
    if (
        override.status == EmployeeCompensationOverride.STATUS_APPROVED
        and override.approval_required
        and any(field in data for field in ("value", "effective_from", "effective_to", "override_type"))
    ):
        override.status = EmployeeCompensationOverride.STATUS_PENDING
        override.approved_by = None
        override.approved_at = None

    override.save()
    after = snapshot(override)
    changed = diff_snapshots(before, after)
    record_override_event(
        override,
        EmployeeCompensationOverrideEvent.EVENT_UPDATED,
        actor=request.user,
        reason=(data.get("reason_for_change") or override.reason),
        old_value=before,
        new_value=after,
        changed_fields=changed,
    )
    _audit(request, "compensation_override_updated", override, changed_fields=changed)
    return Response(override_payload(override, include_history=True))


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


TRANSITIONS = {
    "submit": (
        EmployeeCompensationOverride.STATUS_PENDING,
        EmployeeCompensationOverrideEvent.EVENT_SUBMITTED,
        "compensation_override_submitted",
    ),
    "approve": (
        EmployeeCompensationOverride.STATUS_APPROVED,
        EmployeeCompensationOverrideEvent.EVENT_APPROVED,
        "compensation_override_approved",
    ),
    "reject": (
        EmployeeCompensationOverride.STATUS_REJECTED,
        EmployeeCompensationOverrideEvent.EVENT_REJECTED,
        "compensation_override_rejected",
    ),
    "expire": (
        EmployeeCompensationOverride.STATUS_EXPIRED,
        EmployeeCompensationOverrideEvent.EVENT_EXPIRED,
        "compensation_override_expired",
    ),
}


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def compensation_override_action(request, pk):
    _require_admin(request)
    override = get_object_or_404(_override_queryset(request), pk=pk)

    action = (request.data or {}).get("action")
    if action not in TRANSITIONS:
        raise ValidationError(
            {"action": f"Use one of: {', '.join(sorted(TRANSITIONS))}."}
        )
    new_status, event, audit_action = TRANSITIONS[action]
    reason = ((request.data or {}).get("reason") or "").strip()

    if action == "reject" and not reason:
        raise ValidationError({"reason": "Give a reason for the rejection."})
    if action == "approve" and override.value is None and (
        override.override_type != EmployeeCompensationOverride.TYPE_ELIGIBILITY
    ):
        raise ValidationError({"value": "Set a value before approving."})

    before = snapshot(override)
    override.status = new_status
    if action == "approve":
        override.approved_by = request.user if request.user.is_authenticated else None
        override.approved_at = timezone.now()
    elif action in ("reject", "submit"):
        override.approved_by = None
        override.approved_at = None
    override.save()

    record_override_event(
        override,
        event,
        actor=request.user,
        reason=reason or override.reason,
        old_value=before,
        new_value=snapshot(override),
        changed_fields=["status"],
    )
    _audit(request, audit_action, override, reason=reason)
    return Response(override_payload(override, include_history=True))


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compensation_override_choices(request):
    _require_admin(request)
    approvers = User.objects.filter(is_active=True).order_by(
        "first_name", "last_name", "username"
    )[:200]
    return Response(
        {
            "override_types": [
                {
                    "value": value,
                    "label": label,
                    "default_unit": EmployeeCompensationOverride.DEFAULT_UNIT_FOR_TYPE.get(
                        value
                    ),
                }
                for value, label in EmployeeCompensationOverride.TYPE_CHOICES
            ],
            "statuses": [
                {"value": value, "label": label}
                for value, label in EmployeeCompensationOverride.STATUS_CHOICES
            ],
            "value_units": [
                {"value": value, "label": label}
                for value, label in EmployeeCompensationOverride.UNIT_CHOICES
            ],
            "approvers": [
                {
                    "value": user.id,
                    "label": user.get_full_name() or user.username,
                }
                for user in approvers
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_compensation(request, pk):
    """Full compensation picture for one employee: plan, rules, overrides, history."""
    profile = get_object_or_404(
        filter_queryset_by_organization(UserProfile.objects.all(), _org(request)),
        pk=pk,
    )

    from .people_ops import resolve_plan_for_profile

    plan = resolve_plan_for_profile(profile, organization=_org(request))
    today = timezone.localdate()

    overrides = list(
        EmployeeCompensationOverride.objects.select_related(
            "compensation_plan", "approver", "approved_by", "created_by"
        )
        .filter(employee=profile)
        .order_by("-effective_from", "-id")
    )
    active_ids = set(
        active_overrides_for_employee(profile, today, plan).values_list("id", flat=True)
    )
    history = (
        EmployeeCompensationOverrideEvent.objects.select_related("actor", "override")
        .filter(override__employee=profile)
        .order_by("-created_at", "-id")[:100]
    )

    return Response(
        {
            "employee": {
                "id": profile.id,
                "name": profile.name,
                "employee_id": profile.employee_id,
                "email": profile.email,
                "role": profile.role,
                "department": getattr(profile, "department", ""),
                "business_group": profile.business_group,
                "territory": getattr(profile.territory, "name", "")
                if getattr(profile, "territory", None)
                else "",
                "commission_eligible": getattr(profile, "commission_eligible", True),
            },
            "assigned_plan": (
                {
                    "id": plan.id,
                    "name": plan.plan_name,
                    "status": plan.status,
                    "plan_basis": getattr(plan, "plan_basis", ""),
                    "commission_table_type": plan.commission_table_type,
                    "effective_start_date": (
                        plan.effective_start_date.isoformat()
                        if plan.effective_start_date
                        else None
                    ),
                    "effective_end_date": (
                        plan.effective_end_date.isoformat()
                        if plan.effective_end_date
                        else None
                    ),
                    "is_explicit_assignment": profile.assigned_compensation_plan_id
                    == plan.id,
                }
                if plan
                else None
            ),
            "effective_rules": plan_rules_for_display(plan, today, employee=profile),
            "assigned_commission_rules": plan_rules_for_display(
                plan, today, employee=profile
            ),
            "overrides": [
                {**override_payload(row), "is_active_now": row.id in active_ids}
                for row in overrides
            ],
            "active_override_count": len(active_ids),
            "history": [event_payload(row) for row in history],
            "as_of": today.isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def plan_override_summary(request, plan_id):
    """Who is on this plan and who carries an exception to it."""
    plan = get_object_or_404(
        filter_queryset_by_organization(CompensationPlan.objects.all(), _org(request)),
        pk=plan_id,
    )
    today = timezone.localdate()

    participants = filter_queryset_by_organization(
        UserProfile.objects.filter(assigned_compensation_plan=plan), _org(request)
    ).select_related("territory")

    overrides = (
        EmployeeCompensationOverride.objects.select_related("employee", "approved_by")
        .filter(Q(compensation_plan=plan) | Q(employee__assigned_compensation_plan=plan))
        .order_by("-effective_from", "-id")
        .distinct()
    )
    active = [row for row in overrides if row.is_effective_on(today)]

    by_type = (
        overrides.values("override_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    type_labels = dict(EmployeeCompensationOverride.TYPE_CHOICES)

    return Response(
        {
            "plan": {"id": plan.id, "name": plan.plan_name, "status": plan.status},
            "employees_using_plan": participants.count(),
            "employees_with_overrides": len({row.employee_id for row in active}),
            "override_summary": {
                "total": overrides.count(),
                "active": len(active),
                "pending": overrides.filter(
                    status=EmployeeCompensationOverride.STATUS_PENDING
                ).count(),
                "draft": overrides.filter(
                    status=EmployeeCompensationOverride.STATUS_DRAFT
                ).count(),
                "expired": overrides.filter(
                    status=EmployeeCompensationOverride.STATUS_EXPIRED
                ).count(),
                "by_type": [
                    {
                        "type": row["override_type"],
                        "label": type_labels.get(row["override_type"], row["override_type"]),
                        "count": row["total"],
                    }
                    for row in by_type
                ],
            },
            "overrides": [
                {**override_payload(row), "is_active_now": row.is_effective_on(today)}
                for row in overrides[:200]
            ],
        }
    )


def _audit(request, action, override, reason="", changed_fields=None):
    try:
        record_audit(
            request,
            action,
            detail=(
                f"{override.name} — {override.get_override_type_display()} for "
                f"{override.employee.name or override.employee.email}"
            ),
            entity_type="compensation_override",
            entity_id=str(override.id),
            reason=reason or override.reason,
            changed_fields=changed_fields,
            organization=_org(request),
        )
    except Exception:  # audit must never block a compensation change
        pass
