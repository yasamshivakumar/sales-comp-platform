from django.db import models
from django.utils import timezone
from decimal import Decimal
import logging

from .models import (
    Order,
    CompensationPlan,
    SCRateTable,
    SCFlatRateTable,
    Employee,
    Sale,
    Commission,
    UserProfile,
    HierarchyRelationship,
)

logger = logging.getLogger(__name__)


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
    """Plans active on the order's transaction date."""
    order_date = getattr(order, "order_date", None)
    if not order_date:
        return models.Q()
    return models.Q(effective_start_date__lte=order_date) & (
        models.Q(effective_end_date__isnull=True)
        | models.Q(effective_end_date__gte=order_date)
    )


def _order_has_approved_commissions(order):
    return Commission.objects.filter(
        sale__order=order,
        status=Commission.STATUS_APPROVED,
    ).exists()


def resolve_compensation_plan(order):
    """
    Resolve which Active compensation plan applies to an order.

    Priority:
      1. Position-specific plan (order.position_name, then profile.position_name)
      2. Role-based plan (profile.role) — only plans without a position_name set

    Returns (plan, lookup_source) or (None, None).

    Only plans whose effective_start_date / effective_end_date include order.order_date
    are considered.
    """
    user_profile = _get_user_profile_for_order(order)
    empty_position = models.Q(position_name__isnull=True) | models.Q(position_name="")
    effective = _effective_date_filter(order)

    plan_base = _plan_queryset_for_order(order)

    for pos_name in _position_names_to_try(order, user_profile):
        plan = (
            plan_base.filter(
                position_name=pos_name,
            )
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
                plan_base.filter(
                    role=role,
                )
                .filter(effective)
                .filter(empty_position)
                .order_by("-updated_at")
                .first()
            )
            if plan:
                return plan, f"role:{role}"

    return None, None


def _calculate_amount_for_plan(plan, sales_amount):
    """Apply RATE or FLAT table rules; returns Decimal commission or zero."""
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

    plan, lookup_source = resolve_compensation_plan(order)

    if not plan:
        logger.warning(
            "No compensation plan for order %s "
            "(position_name=%s, employee_id=%s, sales_amount=%s, "
            "order_date=%s, organization_id=%s). "
            "Check: plan status=Active, effective dates include order_date, "
            "position/role match, UserProfile exists for employee_id.",
            order.order_id,
            order.position_name,
            order.employee_id,
            order.sales_amount,
            order.order_date,
            getattr(order, "organization_id", None),
        )
        return None

    logger.info(
        "Plan matched for order %s: plan_id=%s lookup=%s type=%s",
        order.order_id,
        plan.id,
        lookup_source,
        plan.commission_table_type,
    )

    commission_amount = _calculate_amount_for_plan(plan, order.sales_amount)
    if commission_amount <= 0:
        return None

    user_profile = _get_user_profile_for_order(order)
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
    """Mark calculated commissions as approved for payroll."""
    now = timezone.now()
    return queryset.filter(status=Commission.STATUS_CALCULATED).update(
        status=Commission.STATUS_APPROVED,
        approved_at=now,
        approved_by=approved_by_user,
    )


def recalculate_orders_in_range(start_date, end_date, force=True, organization=None):
    """Recalculate commissions for all orders in a date range (admin)."""
    orders = Order.objects.filter(
        order_date__gte=start_date,
        order_date__lte=end_date,
    )
    if organization is not None:
        orders = orders.filter(organization=organization)
    orders = orders.order_by("order_date", "order_id")
    stats = {"processed": 0, "skipped_approved": 0, "failed": 0}
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
