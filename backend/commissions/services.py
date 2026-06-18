from django.db import models
from django.utils import timezone
from decimal import Decimal
import logging

from .models import (
    Order,
    CompensationPlan,
    SCRateTable,
    SCFlatRateTable,
    SCLookupTable,
    Employee,
    Sale,
    Commission,
    UserProfile,
    HierarchyRelationship,
)

logger = logging.getLogger(__name__)

COMMISSION_ELIGIBLE_ORDER_STATUS = "success"


def normalize_order_status(status) -> str:
    return str(status or "").strip().casefold()


def order_is_commission_eligible(order) -> bool:
    """Commissions are created only when order_status is Success."""
    return (
        normalize_order_status(getattr(order, "order_status", None))
        == COMMISSION_ELIGIBLE_ORDER_STATUS
    )


def commission_skip_reason_for_status(order) -> str | None:
    if order_is_commission_eligible(order):
        return None
    status = (getattr(order, "order_status", None) or "Booked").strip() or "Booked"
    return (
        f"Order status is '{status}' — commission is calculated only when status is Success."
    )


def _get_user_profile_for_order(order):
    if not order.employee_id:
        return None
    qs = UserProfile.objects.filter(employee_id=order.employee_id)
    org_id = getattr(order, "organization_id", None)
    if org_id:
        qs = qs.filter(organization_id=org_id)
    return qs.first()


def _plan_queryset_for_order(order):
    qs = CompensationPlan.objects.filter(status="Active")
    org_id = getattr(order, "organization_id", None)
    if org_id:
        # Legacy plans created before multi-tenant may have organization=NULL
        qs = qs.filter(
            models.Q(organization_id=org_id) | models.Q(organization__isnull=True)
        )
    order_territory_id = getattr(order, "territory_id", None)
    if not order_territory_id:
        user_profile = _get_user_profile_for_order(order)
        if user_profile:
            order_territory_id = user_profile.territory_id
    if order_territory_id:
        qs = qs.filter(
            models.Q(territory_id=order_territory_id)
            | models.Q(territory__isnull=True)
        )
    return qs


def _position_names_to_try(order, user_profile):
    """Collect position names from order first, then user profile."""
    names = []
    for value in (
        getattr(order, "position_name", None),
        getattr(user_profile, "position_name", None) if user_profile else None,
    ):
        if value:
            cleaned = str(value).strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
    return names


def _effective_date_filter(order):
    """
    Plans apply only to orders in the same calendar month as the plan period.
    Each month requires its own compensation plan (1st – last day of month).
    """
    from .plan_periods import monthly_plan_filter

    order_date = getattr(order, "order_date", None)
    if not order_date:
        return models.Q()
    return monthly_plan_filter(order_date)


from .workflow import order_has_locked_commissions


def _order_has_approved_commissions(order):
    return order_has_locked_commissions(order)


def resolve_compensation_plan(order):
    """
    Resolve which Active compensation plan applies to an order.

    Priority:
      1. Position-specific plan (order.position_name, then profile.position_name)
      2. Role-based plan (profile.role) — only plans without a position_name set

    Returns (plan, lookup_source) or (None, None).

    Only plans whose month matches order.order_date (year + month) are considered.
    Each calendar month must have its own plan; a January plan never applies to February orders.
    """
    user_profile = _get_user_profile_for_order(order)
    empty_position = models.Q(position_name__isnull=True) | models.Q(position_name="")
    effective = _effective_date_filter(order)

    plan_base = _plan_queryset_for_order(order)

    for pos_name in _position_names_to_try(order, user_profile):
        plan = (
            plan_base.filter(position_name__iexact=pos_name)
            .filter(effective)
            .exclude(position_name__isnull=True)
            .exclude(position_name="")
            .order_by("-updated_at")
            .first()
        )
        if plan:
            return plan, f"position_name:{pos_name}"

    if user_profile and user_profile.role:
        role = str(user_profile.role).strip()
        if role:
            plan = (
                plan_base.filter(role__iexact=role)
                .filter(effective)
                .filter(empty_position)
                .order_by("-updated_at")
                .first()
            )
            if plan:
                return plan, f"role:{role}"

    return None, None


def explain_plan_resolution_failure(order):
    """
    Human-readable reason when resolve_compensation_plan returns None.
    Used by order import warnings and admin diagnostics.
    """
    profile = _get_user_profile_for_order(order)
    position = (getattr(order, "position_name", None) or "").strip()
    order_date = getattr(order, "order_date", None)
    month_label = order_date.strftime("%B %Y") if order_date else "that month"

    if not profile and not position:
        return (
            f"No User Setup profile for employee_id '{order.employee_id}' "
            "and order has no position_name — add the rep in User Setup or "
            "include position_name in the CSV."
        )

    plan_base = _plan_queryset_for_order(order)
    effective = _effective_date_filter(order)
    empty_position = models.Q(position_name__isnull=True) | models.Q(position_name="")

    for pos_name in _position_names_to_try(order, profile):
        pos_plans = (
            plan_base.filter(position_name__iexact=pos_name)
            .exclude(position_name__isnull=True)
            .exclude(position_name="")
        )
        if pos_plans.filter(effective).exists():
            continue
        if pos_plans.exists():
            return (
                f"Position '{pos_name}' has compensation plan(s) but none active for "
                f"{month_label}. Create an Active plan for that month (1st–last day)."
            )

    if profile and profile.role:
        role = str(profile.role).strip()
        if role:
            role_plans = plan_base.filter(role__iexact=role).filter(empty_position)
            if role_plans.exists() and not role_plans.filter(effective).exists():
                return (
                    f"Role '{role}' has compensation plan(s) but none active for "
                    f"{month_label}. Create an Active plan for {month_label} (1st–last day) "
                    f"with role '{role}' and rate tiers."
                )
            if not role_plans.filter(effective).exists():
                month_plans = plan_base.filter(effective)
                roles = sorted(
                    {
                        (p.role or "").strip()
                        for p in month_plans
                        if (p.role or "").strip()
                    }
                )
                user_label = profile.name or profile.employee_id or order.employee_id
                if roles:
                    role_list = ", ".join(f"'{r}'" for r in roles[:6])
                    return (
                        f"User '{user_label}' has role '{role}' but no matching compensation "
                        f"plan for {month_label}. Active plans this month use role(s): "
                        f"{role_list}. Change the user's role in User Setup or create a "
                        f"{month_label} plan for '{role}' (commission rules attach to plans)."
                    )
                return (
                    f"No active compensation plan for role '{role}' in {month_label}. "
                    "Create an Active plan for that month (1st–last day)."
                )

    if not profile:
        return (
            f"No compensation plan matches position_name '{position}' "
            f"for order date {order_date}."
        )

    return (
        f"No active compensation plan for {month_label}. "
        "Check plan status=Active, effective dates, and role/position match."
    )


def _normalize_lookup_token(value) -> str:
    return str(value or "").strip().casefold()


def _lookup_row_matches_order(row, order) -> bool:
    if not order:
        return False
    checks = (
        (row.product_name, order.product_name),
        (row.service_name, order.service_name),
        (row.distribution, getattr(order, "distribution", None)),
    )
    for row_value, order_value in checks:
        needle = _normalize_lookup_token(row_value)
        if needle and needle != _normalize_lookup_token(order_value):
            return False
    return True


def _lookup_row_specificity(row) -> int:
    score = 0
    if _normalize_lookup_token(row.product_name):
        score += 4
    if _normalize_lookup_token(row.service_name):
        score += 2
    if _normalize_lookup_token(row.distribution):
        score += 1
    return score


def _lookup_row_in_sales_band(row, sales_amount) -> bool:
    sales_amount = Decimal(str(sales_amount))
    if row.from_amount > sales_amount:
        return False
    if row.to_amount is not None and row.to_amount < sales_amount:
        return False
    return True


def find_sc_lookup_tier(plan, order, sales_amount):
    """Best matching SC Lookup row for an order and sales amount."""
    if not plan or plan.commission_table_type != "LOOKUP" or not order:
        return None

    candidates = []
    for row in SCLookupTable.objects.filter(
        compensation_plan=plan,
        is_active=True,
    ).order_by("sequence", "id"):
        if not _lookup_row_matches_order(row, order):
            continue
        if not _lookup_row_in_sales_band(row, sales_amount):
            continue
        candidates.append(row)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda row: (_lookup_row_specificity(row), -row.sequence),
    )


def _calculate_amount_for_plan(plan, sales_amount, order=None):
    """Apply RATE, FLAT, or LOOKUP table rules; returns Decimal commission or zero."""
    commission_amount = Decimal("0.00")

    if plan.commission_table_type == "RATE":
        tier = (
            SCRateTable.objects.filter(
                compensation_plan=plan,
                is_active=True,
                from_amount__lte=sales_amount,
            )
            .filter(
                models.Q(to_amount__gte=sales_amount) | models.Q(to_amount__isnull=True)
            )
            .order_by("sequence")
            .first()
        )
        if tier:
            commission_amount = (
                sales_amount * tier.commission_rate / Decimal("100")
            ) + tier.bonus_amount

    elif plan.commission_table_type == "FLAT":
        flat = SCFlatRateTable.objects.filter(
            compensation_plan=plan,
            is_active=True,
            minimum_sales_threshold__lte=sales_amount,
        ).first()
        if flat:
            commission_amount = (
                sales_amount * flat.flat_rate / Decimal("100")
            ) + flat.bonus_amount

    elif plan.commission_table_type == "LOOKUP":
        tier = find_sc_lookup_tier(plan, order, sales_amount)
        if tier:
            commission_amount = (
                sales_amount * tier.commission_rate / Decimal("100")
            ) + tier.bonus_amount

    return commission_amount


def _get_or_create_employee_for_order(order, user_profile):
    if user_profile:
        employee, _ = Employee.objects.get_or_create(
            email=user_profile.email,
            defaults={
                "name": user_profile.name or user_profile.employee_id,
            },
        )
        return employee

    employee, _ = Employee.objects.get_or_create(
        email=f"{order.employee_id}@company.com",
        defaults={"name": order.employee_id or "Unknown"},
    )
    return employee


def _apply_hierarchy_split(order, commission_amount):
    """
    split_percentage on HierarchyRelationship = percent retained by the child (seller).
    Default 100 means the seller keeps the full calculated commission.
    Parent receives the remainder (manager override).
    """
    employee_amount = commission_amount
    parent_amount = Decimal("0.00")
    parent_employee = None

    if not order.employee_id:
        return employee_amount, parent_amount, parent_employee

    user_profile = _get_user_profile_for_order(order)
    if not user_profile:
        return employee_amount, parent_amount, parent_employee

    try:
        hierarchy = HierarchyRelationship.objects.filter(
            child_participant=user_profile,
            is_active=True,
        ).first()

        if not hierarchy or not hierarchy.parent_participant:
            return employee_amount, parent_amount, parent_employee

        child_pct = Decimal(str(hierarchy.split_percentage))
        child_pct = min(max(child_pct, Decimal("0")), Decimal("100"))

        employee_amount = (commission_amount * child_pct) / Decimal("100")
        parent_amount = commission_amount - employee_amount

        if parent_amount > 0:
            parent_user = hierarchy.parent_participant
            parent_name = (
                parent_user.name
                or f"{parent_user.first_name} {parent_user.last_name}".strip()
                or parent_user.email
            )
            parent_employee, _ = Employee.objects.get_or_create(
                email=parent_user.email,
                defaults={"name": parent_name},
            )
    except Exception as exc:
        logger.exception(
            "Hierarchy split failed for order %s: %s", order.order_id, exc
        )

    return employee_amount, parent_amount, parent_employee


def clear_commissions_for_order(order, force=False):
    """
    Remove prior sale/commission rows for this order (idempotent re-runs).

    Skips deletion when approved commissions exist unless force=True (admin recalc).
    """
    if not order or not order.pk:
        return 0
    if not force and _order_has_approved_commissions(order):
        logger.warning(
            "Skipping commission recalc for order %s: approved commissions exist",
            order.order_id,
        )
        return 0
    deleted, _ = Sale.objects.filter(order=order).delete()
    return deleted


def calculate_commission_for_order(order, replace_existing=True, force=False):
    """
    Calculate commission for one order and persist Commission record(s).

    Plan lookup priority:
      1. Active plan matching position_name (order, then user profile)
      2. Active role-based plan (no position_name on plan)

    Hierarchy:
      split_percentage = % of commission kept by the child; parent gets the rest.

    replace_existing: If True, delete existing commissions for this order first.
    force: Allow replacing approved commissions (admin bulk recalc).
    """
    if replace_existing:
        if not force and _order_has_approved_commissions(order):
            logger.warning(
                "Commission calc skipped for order %s (approved, use force recalc)",
                order.order_id,
            )
            return None
        clear_commissions_for_order(order, force=force)

    if not order_is_commission_eligible(order):
        logger.info(
            "Commission calc skipped for order %s: status=%s (requires Success)",
            order.order_id,
            getattr(order, "order_status", None),
        )
        return None

    plan, lookup_source = resolve_compensation_plan(order)

    if not plan:
        user_profile = _get_user_profile_for_order(order)
        logger.warning(
            "No compensation plan for order %s "
            "(position_name=%s, employee_id=%s, profile_role=%s, sales_amount=%s, "
            "order_date=%s, organization_id=%s). %s",
            order.order_id,
            order.position_name,
            order.employee_id,
            getattr(user_profile, "role", None),
            order.sales_amount,
            order.order_date,
            getattr(order, "organization_id", None),
            explain_plan_resolution_failure(order),
        )
        return None

    logger.info(
        "Plan matched for order %s: plan_id=%s lookup=%s type=%s",
        order.order_id,
        plan.id,
        lookup_source,
        plan.commission_table_type,
    )

    commission_amount = _calculate_amount_for_plan(plan, order.sales_amount, order=order)
    if commission_amount <= 0:
        return None

    from .commission_rules import apply_commission_rules

    user_profile = _get_user_profile_for_order(order)
    commission_amount, credit_amount, matched_rule, rule_meta = apply_commission_rules(
        plan, order, user_profile, commission_amount
    )
    if commission_amount <= 0:
        return None

    employee = _get_or_create_employee_for_order(order, user_profile)

    sale = Sale.objects.create(
        order=order,
        employee=employee,
        employee_salary=Decimal("0.00"),
        amount=order.sales_amount,
    )

    employee_amount, parent_amount, parent_employee = _apply_hierarchy_split(
        order, commission_amount
    )

    commission = Commission.objects.create(
        employee=employee,
        sale=sale,
        commission_amount=employee_amount,
        compensation_plan=plan,
        commission_rule=matched_rule,
        credit_amount=credit_amount,
        result_classification=rule_meta.get("result_classification", ""),
        earning_group=rule_meta.get("earning_group", ""),
        hold_until=rule_meta.get("hold_until"),
        reason_code=rule_meta.get("reason_code", ""),
        rule_result_name=rule_meta.get("rule_result_name", ""),
        status=Commission.STATUS_CALCULATED,
    )

    if parent_employee and parent_amount > 0:
        Commission.objects.create(
            employee=parent_employee,
            sale=sale,
            commission_amount=parent_amount,
            compensation_plan=plan,
            status=Commission.STATUS_CALCULATED,
        )

    return commission


def approve_commissions(queryset, approved_by_user):
    """Legacy: admin shortcut to finance-approved (skips manager step)."""
    from .workflow import approve_commissions_admin_shortcut
    return approve_commissions_admin_shortcut(queryset, approved_by_user)


def recalculate_orders_in_range(
    start_date, end_date, force=True, organization=None, employee_q=None
):
    """Recalculate commissions for orders in a date range (admin)."""
    orders = Order.objects.filter(
        order_date__gte=start_date,
        order_date__lte=end_date,
    )
    if organization is not None:
        orders = orders.filter(organization=organization)
    employee_q = (employee_q or "").strip()
    if employee_q:
        from .list_scope import order_employee_search_q

        orders = orders.filter(order_employee_search_q(employee_q))
    orders = orders.order_by("order_date", "order_id")
    stats = {
        "processed": 0,
        "skipped_approved": 0,
        "failed": 0,
        "employee_q": employee_q,
        "scoped": bool(employee_q),
        "order_count": orders.count(),
    }
    for order in orders:
        if not force and _order_has_approved_commissions(order):
            stats["skipped_approved"] += 1
            continue
        try:
            calculate_commission_for_order(
                order, replace_existing=True, force=force
            )
            stats["processed"] += 1
        except Exception:
            logger.exception("Recalc failed for order %s", order.order_id)
            stats["failed"] += 1
    return stats
