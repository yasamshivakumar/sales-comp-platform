"""Helpers for assigning commission rules to individual employees."""

from django.db.models import Q

from rest_framework.exceptions import ValidationError

from .models import (
    CompensationPlan,
    CommissionRule,
    EmployeeCommissionRuleAssignment,
    UserProfile,
)


def rule_plan_id(rule):
    """Compensation plan id for a rule (direct or via plan version)."""
    if getattr(rule, "compensation_plan_id", None):
        return rule.compensation_plan_id
    version = getattr(rule, "plan_version", None)
    if version is not None:
        return getattr(version, "compensation_plan_id", None)
    return None


def employees_queryset_for_plan(plan_id, organization=None, search=None):
    """
    Employees eligible for a commission rule on this compensation plan.

    Matches People & Access "assigned plan" semantics:
    - explicitly assigned to this plan (UserProfile.assigned_compensation_plan), OR
    - no explicit plan, and resolve_plan_for_profile would pick this plan
      (same role/position fallback People uses)

    People locked to a *different* plan are never returned.
    Never returns other tenants.
    """
    if not plan_id:
        return UserProfile.objects.none()
    try:
        plan_id = int(plan_id)
    except (TypeError, ValueError):
        return UserProfile.objects.none()

    plan = CompensationPlan.objects.filter(pk=plan_id).first()
    if plan is None:
        return UserProfile.objects.none()
    if organization is not None:
        org_id = getattr(organization, "id", organization)
        if plan.organization_id not in (None, org_id):
            return UserProfile.objects.none()

    from .people_ops import resolve_plan_for_profile
    from .plan_catalog import participants_queryset_for_plan

    org = organization if organization is not None else plan.organization

    # Explicit assignees always belong to this plan.
    explicit = UserProfile.objects.filter(assigned_compensation_plan_id=plan_id)
    if org is not None:
        explicit = explicit.filter(organization=org)

    # Unassigned people who match this plan's role/position, but only when
    # People would resolve them to *this* plan (not a sibling plan with the
    # same role). That prevents Laxmi appearing on both "Sales Rep" and
    # "Sales Reps".
    unassigned_ids = []
    candidates = participants_queryset_for_plan(plan, org).filter(
        assigned_compensation_plan_id__isnull=True
    )
    for profile in candidates.iterator(chunk_size=200):
        resolved = resolve_plan_for_profile(profile, org)
        if resolved is not None and resolved.id == plan_id:
            unassigned_ids.append(profile.id)

    if unassigned_ids:
        unassigned = UserProfile.objects.filter(pk__in=unassigned_ids)
        qs = (explicit | unassigned).distinct()
    else:
        qs = explicit

    term = (search or "").strip()
    if term:
        qs = qs.filter(
            Q(name__icontains=term)
            | Q(employee_id__icontains=term)
            | Q(email__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
        )

    return qs.select_related("assigned_compensation_plan", "organization").order_by(
        "name", "employee_id"
    )


def employee_belongs_to_plan(employee, plan_id, organization=None):
    """True when employee's effective plan (People semantics) is this plan."""
    if employee is None or not plan_id:
        return False
    try:
        plan_id = int(plan_id)
    except (TypeError, ValueError):
        return False
    if organization is not None:
        org_id = getattr(organization, "id", organization)
        emp_org = getattr(employee, "organization_id", None)
        if emp_org is not None and emp_org != org_id:
            return False

    emp_plan = getattr(employee, "assigned_compensation_plan_id", None)
    if emp_plan == plan_id:
        return True
    if emp_plan:
        return False

    from .people_ops import resolve_plan_for_profile

    org = organization if organization is not None else getattr(employee, "organization", None)
    resolved = resolve_plan_for_profile(employee, org)
    return resolved is not None and resolved.id == plan_id


def serialize_eligible_employee(row):
    """API payload for one plan-scoped employee in the assignee picker."""
    status_raw = (getattr(row, "account_status", None) or "").strip().lower()
    if status_raw in ("suspended", "deactivated", "inactive"):
        status = "inactive"
    else:
        status = "active"
    job_title = (
        (getattr(row, "title", None) or "").strip()
        or (getattr(row, "position_title", None) or "").strip()
        or (getattr(row, "role", None) or "").strip()
        or ""
    )
    display_name = (
        (getattr(row, "name", None) or "").strip()
        or " ".join(
            p
            for p in [
                getattr(row, "first_name", None) or "",
                getattr(row, "last_name", None) or "",
            ]
            if p
        ).strip()
        or getattr(row, "email", "")
        or f"Employee #{row.id}"
    )
    emp_plan = row.assigned_compensation_plan_id
    return {
        "id": row.id,
        "name": display_name,
        "employee_id": getattr(row, "employee_id", "") or "",
        "email": getattr(row, "email", "") or "",
        "job_title": job_title,
        "role": getattr(row, "role", "") or "",
        "status": status,
        "account_status": getattr(row, "account_status", "") or "",
        "assigned_compensation_plan": emp_plan,
        "plan_assigned": emp_plan is not None,
    }


def validate_employees_for_rule(rule, employee_ids, organization=None):
    """
    Return UserProfile rows ready to assign.

    Employees must match the rule's plan using the same effective-plan rules
    as People & Access (explicit FK or role/position resolve). People locked
    to a different plan are rejected.
    """
    ids = []
    seen = set()
    for raw in employee_ids or []:
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            raise ValidationError({"employee_ids": f"Invalid employee id: {raw}"})
        if pk in seen:
            continue
        seen.add(pk)
        ids.append(pk)

    if not ids:
        return []

    plan_id = rule_plan_id(rule)
    if not plan_id:
        raise ValidationError(
            {
                "employee_ids": (
                    "Select a compensation plan on this rule before assigning employees."
                )
            }
        )

    qs = UserProfile.objects.filter(pk__in=ids)
    if organization is not None:
        qs = qs.filter(organization=organization)
    elif getattr(rule, "organization_id", None):
        qs = qs.filter(organization_id=rule.organization_id)

    found = {row.id: row for row in qs}
    missing = [pk for pk in ids if pk not in found]
    if missing:
        raise ValidationError(
            {
                "employee_ids": (
                    "Employees not found in this organization: "
                    f"{missing}"
                )
            }
        )

    eligible_ids = set(
        employees_queryset_for_plan(plan_id, organization=organization)
        .filter(pk__in=ids)
        .values_list("id", flat=True)
    )
    incompatible = [pk for pk in ids if pk not in eligible_ids]
    if incompatible:
        raise ValidationError(
            {
                "employee_ids": (
                    "Only employees on this rule's compensation plan "
                    f"(plan id {plan_id}) can be selected. "
                    f"Incompatible employee ids: {sorted(set(incompatible))}"
                )
            }
        )

    return [found[pk] for pk in ids]


def _ensure_employees_on_plan(employees, plan_id):
    """Persist plan FK for previously unassigned people when a rule is saved."""
    to_update = [emp for emp in employees if emp.assigned_compensation_plan_id is None]
    if not to_update:
        return
    for emp in to_update:
        emp.assigned_compensation_plan_id = plan_id
    UserProfile.objects.bulk_update(to_update, ["assigned_compensation_plan_id"])


def sync_rule_assignments(rule, employee_ids, organization=None, assigned_by=None):
    """
    Replace all assignments for a rule with employee_ids (idempotent).

    Requires at least one employee. Returns (added_count, removed_count, current_ids).
    Unassigned eligible employees are auto-assigned to this plan on save.
    """
    if not employee_ids:
        raise ValidationError(
            {
                "assigned_employee_ids": (
                    "Select at least one employee. A Commission Rule must be assigned "
                    "to one or more employees on its Compensation Plan."
                )
            }
        )
    employees = validate_employees_for_rule(rule, employee_ids, organization)
    plan_id = rule_plan_id(rule)
    if plan_id:
        _ensure_employees_on_plan(employees, plan_id)
    desired = {emp.id for emp in employees}
    current = set(
        EmployeeCommissionRuleAssignment.objects.filter(rule=rule).values_list(
            "employee_id", flat=True
        )
    )

    to_remove = current - desired
    to_add = desired - current

    if to_remove:
        EmployeeCommissionRuleAssignment.objects.filter(
            rule=rule, employee_id__in=to_remove
        ).delete()

    org_id = getattr(organization, "id", None) or getattr(rule, "organization_id", None)
    new_rows = []
    emp_by_id = {e.id: e for e in employees}
    for emp_id in to_add:
        emp = emp_by_id[emp_id]
        new_rows.append(
            EmployeeCommissionRuleAssignment(
                organization_id=org_id or emp.organization_id,
                employee_id=emp_id,
                rule=rule,
                assigned_by=assigned_by,
            )
        )
    if new_rows:
        EmployeeCommissionRuleAssignment.objects.bulk_create(
            new_rows, ignore_conflicts=True
        )

    return len(to_add), len(to_remove), sorted(desired)


def add_rule_assignments(rule, employee_ids, organization=None, assigned_by=None):
    """Add assignments without removing existing ones. Returns added employee ids."""
    employees = validate_employees_for_rule(rule, employee_ids, organization)
    plan_id = rule_plan_id(rule)
    if plan_id:
        _ensure_employees_on_plan(employees, plan_id)
    existing = set(
        EmployeeCommissionRuleAssignment.objects.filter(rule=rule).values_list(
            "employee_id", flat=True
        )
    )
    org_id = getattr(organization, "id", None) or getattr(rule, "organization_id", None)
    added = []
    rows = []
    for emp in employees:
        if emp.id in existing:
            continue
        rows.append(
            EmployeeCommissionRuleAssignment(
                organization_id=org_id or emp.organization_id,
                employee_id=emp.id,
                rule=rule,
                assigned_by=assigned_by,
            )
        )
        added.append(emp.id)
    if rows:
        EmployeeCommissionRuleAssignment.objects.bulk_create(
            rows, ignore_conflicts=True
        )
    return added


def remove_rule_assignments(rule, employee_ids):
    """Remove specific assignments. Returns removed count."""
    ids = []
    for raw in employee_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return 0
    deleted, _ = EmployeeCommissionRuleAssignment.objects.filter(
        rule=rule, employee_id__in=ids
    ).delete()
    return deleted


def assignment_is_valid(assignment, rule=None):
    """True when the assignee is explicitly assigned to the rule's compensation plan."""
    rule = rule or assignment.rule
    plan_id = rule_plan_id(rule)
    emp = getattr(assignment, "employee", None)
    if emp is None and assignment.employee_id:
        emp = UserProfile.objects.filter(pk=assignment.employee_id).first()
    org = getattr(emp, "organization", None) if emp is not None else None
    return employee_belongs_to_plan(emp, plan_id, organization=org)


def find_invalid_assignments(organization=None):
    """
    Return assignments where the employee is not on the rule's compensation plan.

    These must not be used in calculation until corrected (removed or employee
    moved onto the rule's plan).
    """
    qs = EmployeeCommissionRuleAssignment.objects.select_related(
        "employee",
        "rule",
        "rule__compensation_plan",
        "rule__plan_version",
        "rule__plan_version__compensation_plan",
    )
    if organization is not None:
        qs = qs.filter(
            Q(organization=organization)
            | Q(rule__organization=organization)
            | Q(employee__organization=organization)
        )

    invalid = []
    for row in qs.iterator(chunk_size=200):
        if not assignment_is_valid(row):
            plan_id = rule_plan_id(row.rule)
            emp_plan = getattr(row.employee, "assigned_compensation_plan_id", None)
            invalid.append(
                {
                    "assignment_id": row.id,
                    "rule_id": row.rule_id,
                    "rule_name": getattr(row.rule, "name", ""),
                    "rule_plan_id": plan_id,
                    "rule_plan_name": getattr(
                        getattr(row.rule, "compensation_plan", None), "plan_name", ""
                    )
                    or getattr(
                        getattr(
                            getattr(row.rule, "plan_version", None),
                            "compensation_plan",
                            None,
                        ),
                        "plan_name",
                        "",
                    ),
                    "employee_id": row.employee_id,
                    "employee_name": getattr(row.employee, "name", "")
                    or getattr(row.employee, "email", ""),
                    "employee_code": getattr(row.employee, "employee_id", ""),
                    "employee_plan_id": emp_plan,
                    "reason": (
                        "Employee has no assigned compensation plan"
                        if not emp_plan
                        else "Employee compensation plan does not match the rule's plan"
                    ),
                }
            )
    return invalid


def valid_assigned_rule_ids_for_employee(user_profile):
    """
    Rule ids that apply to this employee:
    - explicit EmployeeCommissionRuleAssignment (plan still covers them), OR
    - active rules with apply_to_all_plan_participants on a plan they belong to.
    """
    if user_profile is None or not getattr(user_profile, "pk", None):
        return CommissionRule.objects.none().values_list("id", flat=True)

    org = getattr(user_profile, "organization", None)
    emp_plan_id = getattr(user_profile, "assigned_compensation_plan_id", None)

    qs = EmployeeCommissionRuleAssignment.objects.filter(employee_id=user_profile.pk)
    if emp_plan_id:
        explicit_ids = set(
            qs.filter(
                Q(rule__compensation_plan_id=emp_plan_id)
                | Q(rule__plan_version__compensation_plan_id=emp_plan_id)
            ).values_list("rule_id", flat=True)
        )
    else:
        explicit_ids = {
            row.rule_id
            for row in qs.select_related("rule", "rule__plan_version")
            if employee_belongs_to_plan(
                user_profile, rule_plan_id(row.rule), organization=org
            )
        }

    plan_wide = CommissionRule.objects.filter(
        apply_to_all_plan_participants=True,
        is_active=True,
    ).select_related("compensation_plan", "plan_version")
    if org is not None:
        plan_wide = plan_wide.filter(
            Q(organization=org) | Q(organization__isnull=True)
        )

    plan_wide_ids = set()
    for rule in plan_wide.iterator(chunk_size=100):
        pid = rule_plan_id(rule)
        if pid and employee_belongs_to_plan(user_profile, pid, organization=org):
            plan_wide_ids.add(rule.id)

    combined = explicit_ids | plan_wide_ids
    return CommissionRule.objects.filter(id__in=combined).values_list("id", flat=True)


def assignment_payload(assignment):
    emp = assignment.employee
    plan_id = rule_plan_id(assignment.rule) if getattr(assignment, "rule", None) else None
    emp_plan = emp.assigned_compensation_plan_id
    valid = employee_belongs_to_plan(
        emp, plan_id, organization=getattr(emp, "organization", None)
    )
    return {
        "id": emp.id,
        "name": getattr(emp, "name", "") or getattr(emp, "email", ""),
        "employee_id": getattr(emp, "employee_id", ""),
        "email": getattr(emp, "email", ""),
        "assigned_compensation_plan": emp_plan,
        "assigned_at": assignment.assigned_at.isoformat()
        if assignment.assigned_at
        else None,
        "is_valid": valid,
        "invalid_reason": (
            None
            if valid
            else (
                "Employee is assigned to a different compensation plan"
                if emp_plan and emp_plan != plan_id
                else "Employee is not eligible for this compensation plan"
            )
        ),
    }
