"""Employee compensation overrides: resolution, application and history.

Hierarchy enforced here:

    Compensation Plan -> Commission Rules -> Employee Assignment
        -> Employee Overrides (optional) -> Commission Calculation

Overrides are exceptions layered on an assigned plan, never replacements for
it. A single plan therefore keeps serving every employee on it while
individual people carry temporary or permanent exceptions.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from .models import (
    CommissionRule,
    EmployeeCompensationOverride,
    EmployeeCompensationOverrideEvent,
    UserProfile,
)

# Priority 1 in the evaluation hierarchy; plan-owned rules start at 2.
OVERRIDE_PRIORITY = 1

# Applied in this order so a rate override sets the base before accelerators,
# multipliers and flat adjustments layer on top of it.
APPLY_ORDER = [
    EmployeeCompensationOverride.TYPE_ELIGIBILITY,
    EmployeeCompensationOverride.TYPE_COMMISSION_RATE,
    EmployeeCompensationOverride.TYPE_ACCELERATOR,
    EmployeeCompensationOverride.TYPE_MULTIPLIER,
    EmployeeCompensationOverride.TYPE_BONUS,
    EmployeeCompensationOverride.TYPE_DRAW,
    EmployeeCompensationOverride.TYPE_RECOVERY,
]

# Types that change the payout maths. Quota only shifts attainment targets.
MONETARY_TYPES = set(APPLY_ORDER)


def to_decimal(value, default=Decimal("0")):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def active_overrides_for_employee(profile, on_date=None, plan=None):
    """Approved overrides covering ``on_date`` for this employee, priority first."""
    if profile is None:
        return EmployeeCompensationOverride.objects.none()

    on_date = on_date or timezone.localdate()
    qs = EmployeeCompensationOverride.objects.filter(
        employee=profile,
        status=EmployeeCompensationOverride.STATUS_APPROVED,
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))

    if plan is not None:
        # A blank plan on the override means "whatever plan the employee is on".
        qs = qs.filter(Q(compensation_plan__isnull=True) | Q(compensation_plan=plan))

    return qs.order_by("priority", "-effective_from", "-id")


def resolve_overrides_by_type(profile, on_date=None, plan=None):
    """Newest effective override per type, so a later exception wins."""
    resolved = {}
    for override in active_overrides_for_employee(profile, on_date, plan):
        resolved.setdefault(override.override_type, override)
    return resolved


def profile_for_order(order, user_profile=None):
    if user_profile is not None:
        return user_profile
    employee_id = getattr(order, "employee_id", None)
    if not employee_id:
        return None
    qs = UserProfile.objects.filter(employee_id=employee_id)
    organization = getattr(order, "organization", None)
    if organization is not None:
        qs = qs.filter(organization=organization)
    return qs.first()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def _describe(override):
    return {
        "id": override.id,
        "name": override.name,
        "type": override.override_type,
        "type_label": override.get_override_type_display(),
        "value": str(override.value) if override.value is not None else None,
        "unit": override.value_unit,
        "effective_from": (
            override.effective_from.isoformat() if override.effective_from else None
        ),
        "effective_to": (
            override.effective_to.isoformat() if override.effective_to else None
        ),
        "reason": override.reason,
        "priority": override.priority,
    }


def apply_employee_overrides(
    profile, order, base_amount, sales_amount, on_date=None, plan=None
):
    """Layer approved overrides onto the plan's base amount.

    Returns ``(amount, applied, suppress_plan_rules, trace)`` where ``applied``
    is the primary override recorded on the commission (the rate override when
    present, otherwise the first one that changed the payout).
    """
    amount = to_decimal(base_amount)
    sales_amount = to_decimal(sales_amount)
    trace = {"evaluated": [], "applied": [], "eligible": True}

    overrides = resolve_overrides_by_type(profile, on_date=on_date, plan=plan)
    if not overrides:
        return amount, None, False, trace

    primary = None
    suppress_plan_rules = False

    for override_type in APPLY_ORDER:
        override = overrides.get(override_type)
        if override is None:
            continue

        value = to_decimal(override.value)
        before = amount
        trace["evaluated"].append(_describe(override))

        if override_type == EmployeeCompensationOverride.TYPE_ELIGIBILITY:
            if value <= 0:
                trace["eligible"] = False
                trace["applied"].append(
                    {**_describe(override), "amount_before": str(before), "amount_after": "0"}
                )
                return Decimal("0"), override, True, trace
            continue

        if override_type == EmployeeCompensationOverride.TYPE_COMMISSION_RATE:
            amount = sales_amount * value / Decimal("100")
        elif override_type == EmployeeCompensationOverride.TYPE_ACCELERATOR:
            amount = amount + (sales_amount * value / Decimal("100"))
        elif override_type == EmployeeCompensationOverride.TYPE_MULTIPLIER:
            amount = amount * (value if value else Decimal("1"))
        elif override_type == EmployeeCompensationOverride.TYPE_BONUS:
            amount = amount + value
        elif override_type == EmployeeCompensationOverride.TYPE_DRAW:
            # A draw guarantees a floor for the period.
            amount = max(amount, value)
        elif override_type == EmployeeCompensationOverride.TYPE_RECOVERY:
            amount = max(Decimal("0"), amount - value)

        trace["applied"].append(
            {
                **_describe(override),
                "amount_before": str(before),
                "amount_after": str(amount),
            }
        )
        if primary is None or override_type == (
            EmployeeCompensationOverride.TYPE_COMMISSION_RATE
        ):
            primary = override
        if override.stop_on_match:
            suppress_plan_rules = True

    return amount, primary, suppress_plan_rules, trace


# ---------------------------------------------------------------------------
# History & lifecycle
# ---------------------------------------------------------------------------


def snapshot(override):
    """Serialisable value snapshot used for old/new comparisons in history."""
    return {
        "name": override.name,
        "override_type": override.override_type,
        "value": str(override.value) if override.value is not None else None,
        "value_unit": override.value_unit,
        "status": override.status,
        "effective_from": (
            override.effective_from.isoformat() if override.effective_from else None
        ),
        "effective_to": (
            override.effective_to.isoformat() if override.effective_to else None
        ),
        "compensation_plan_id": override.compensation_plan_id,
        "approval_required": override.approval_required,
        "approver_id": override.approver_id,
        "reason": override.reason,
    }


def diff_snapshots(before, after):
    return sorted(
        key for key in set(before) | set(after) if before.get(key) != after.get(key)
    )


def record_override_event(
    override,
    event,
    actor=None,
    reason="",
    old_value=None,
    new_value=None,
    changed_fields=None,
):
    return EmployeeCompensationOverrideEvent.objects.create(
        override=override,
        override_name=override.name,
        event=event,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        reason=reason or override.reason or "",
        old_value=old_value or {},
        new_value=new_value or {},
        changed_fields=changed_fields or [],
        status_after=override.status,
        effective_from=override.effective_from,
        effective_to=override.effective_to,
    )


def expire_due_overrides(organization=None, actor=None):
    """Flip approved overrides whose window has closed to Expired."""
    today = timezone.localdate()
    qs = EmployeeCompensationOverride.objects.filter(
        status=EmployeeCompensationOverride.STATUS_APPROVED,
        effective_to__isnull=False,
        effective_to__lt=today,
    )
    if organization is not None:
        qs = qs.filter(organization=organization)

    expired = 0
    for override in qs:
        before = snapshot(override)
        override.status = EmployeeCompensationOverride.STATUS_EXPIRED
        override.save(update_fields=["status", "updated_at"])
        record_override_event(
            override,
            EmployeeCompensationOverrideEvent.EVENT_EXPIRED,
            actor=actor,
            reason=f"Effective window ended {override.effective_to}",
            old_value=before,
            new_value=snapshot(override),
            changed_fields=["status"],
        )
        expired += 1
    return expired


# ---------------------------------------------------------------------------
# Read models for the UI
# ---------------------------------------------------------------------------


def _rule_summary(rule):
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "rule_type_label": rule.get_rule_type_display(),
        "scope": rule.scope,
        "scope_label": rule.get_scope_display(),
        "priority": rule.priority,
        "sequence": rule.sequence,
        "condition_logic": rule.condition_logic,
        "multiplier": str(rule.multiplier),
        "effective_start_date": (
            rule.effective_start_date.isoformat() if rule.effective_start_date else None
        ),
        "effective_end_date": (
            rule.effective_end_date.isoformat() if rule.effective_end_date else None
        ),
        "conditions": [
            {
                "field": condition.field,
                "field_label": condition.get_field_display(),
                "operator": condition.operator,
                "operator_label": condition.get_operator_display(),
                "value": condition.value,
            }
            for condition in rule.conditions.filter(is_active=True)
        ],
        "results": [
            {
                "name": result.result_name,
                "rate_type": result.result_rate_type,
                "rate_type_label": result.get_result_rate_type_display(),
                "rate_value": (
                    str(result.rate_value) if result.rate_value is not None else None
                ),
                "classification": result.result_classification,
                "earning_group": result.earning_group,
            }
            for result in rule.results.filter(is_active=True)
        ],
    }


def plan_rules_for_display(plan, on_date=None):
    """Currently effective rules of a plan, in evaluation order."""
    if plan is None:
        return []

    from .commission_rules import rule_is_effective

    on_date = on_date or timezone.localdate()
    published = (
        plan.versions.filter(status="Published").order_by("-version_number").first()
        if hasattr(plan, "versions")
        else None
    )
    if published is not None:
        qs = CommissionRule.objects.filter(plan_version=published, is_active=True)
    else:
        qs = CommissionRule.objects.filter(compensation_plan=plan, is_active=True)

    qs = qs.prefetch_related("conditions", "results").order_by(
        "priority", "sequence", "id"
    )
    return [_rule_summary(rule) for rule in qs if rule_is_effective(rule, on_date)]


def override_payload(override, include_history=False):
    data = {
        "id": override.id,
        "name": override.name,
        "employee_id": override.employee_id,
        "employee_name": getattr(override.employee, "name", "")
        or getattr(override.employee, "email", ""),
        "employee_code": getattr(override.employee, "employee_id", ""),
        "compensation_plan": override.compensation_plan_id,
        "compensation_plan_name": getattr(
            override.compensation_plan, "plan_name", ""
        ),
        "override_type": override.override_type,
        "override_type_label": override.get_override_type_display(),
        "value": str(override.value) if override.value is not None else None,
        "value_unit": override.value_unit,
        "previous_value": (
            str(override.previous_value)
            if override.previous_value is not None
            else None
        ),
        "effective_from": (
            override.effective_from.isoformat() if override.effective_from else None
        ),
        "effective_to": (
            override.effective_to.isoformat() if override.effective_to else None
        ),
        "reason": override.reason,
        "priority": override.priority,
        "stop_on_match": override.stop_on_match,
        "approval_required": override.approval_required,
        "approver": override.approver_id,
        "approver_name": (
            override.approver.get_full_name() or override.approver.username
            if override.approver
            else ""
        ),
        "status": override.status,
        "status_label": override.get_status_display(),
        "approved_by_name": (
            override.approved_by.get_full_name() or override.approved_by.username
            if override.approved_by
            else ""
        ),
        "approved_at": override.approved_at.isoformat() if override.approved_at else None,
        "created_by_name": (
            override.created_by.get_full_name() or override.created_by.username
            if override.created_by
            else ""
        ),
        "created_at": override.created_at.isoformat() if override.created_at else None,
        "updated_at": override.updated_at.isoformat() if override.updated_at else None,
        "is_effective_today": override.is_effective_on(timezone.localdate()),
    }
    if include_history:
        data["history"] = [event_payload(e) for e in override.history.all()[:50]]
    return data


def event_payload(event):
    return {
        "id": event.id,
        "override": event.override_id,
        "override_name": event.override_name,
        "event": event.event,
        "event_label": event.get_event_display(),
        "actor_name": (
            event.actor.get_full_name() or event.actor.username if event.actor else "System"
        ),
        "reason": event.reason,
        "old_value": event.old_value,
        "new_value": event.new_value,
        "changed_fields": event.changed_fields,
        "status_after": event.status_after,
        "effective_from": (
            event.effective_from.isoformat() if event.effective_from else None
        ),
        "effective_to": event.effective_to.isoformat() if event.effective_to else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
