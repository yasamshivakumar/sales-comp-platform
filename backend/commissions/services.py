from django.db import models
from django.utils import timezone
from decimal import Decimal
import logging

from .currencies import normalize_currency
from .models import (
    Order,
    CommissionPlanVersion,
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


def _profile_for_employee(employee_id, organization=None):
    if not employee_id:
        return None
    from .tenants import allow_default_organization_fallback

    qs = UserProfile.objects.filter(employee_id__iexact=employee_id)
    if organization is not None:
        profile = qs.filter(organization=organization).first()
        if profile:
            return profile
        if allow_default_organization_fallback():
            return qs.filter(organization__isnull=True).first()
        return None
    if allow_default_organization_fallback():
        return qs.filter(organization__isnull=True).first() or qs.first()
    return qs.exclude(organization__isnull=True).first()


def _get_user_profile_for_order(order):
    if not order.employee_id:
        return None
    return _profile_for_employee(
        order.employee_id,
        getattr(order, "organization", None),
    )


def derive_order_business_group(order, profile=None):
    """Resolve business group: explicit field → currency → plan → employee profile."""
    from .business_groups import (
        business_group_for_currency,
        normalize_business_group,
    )

    explicit = str(getattr(order, "business_group", None) or "").strip()
    if explicit:
        return normalize_business_group(explicit, default="")

    currency = str(getattr(order, "currency", None) or "").strip()
    if currency:
        from_currency = business_group_for_currency(currency)
        if from_currency:
            return from_currency

    profile = profile or _get_user_profile_for_order(order)
    plan, _source = resolve_compensation_plan(order)
    if plan and str(plan.business_group or "").strip():
        return normalize_business_group(plan.business_group, default="")
    if profile and str(profile.business_group or "").strip():
        return normalize_business_group(profile.business_group, default="")
    return ""


def derive_order_currency(order, profile=None):
    """Best currency for an order — respects explicit order.currency before profile."""
    from .business_groups import currency_for_business_group

    if str(getattr(order, "currency", None) or "").strip():
        return normalize_currency(getattr(order, "currency", None))

    explicit_group = str(getattr(order, "business_group", None) or "").strip()
    if explicit_group:
        return currency_for_business_group(explicit_group)

    profile = profile or _get_user_profile_for_order(order)
    plan, _source = resolve_compensation_plan(order)
    if plan and str(plan.business_group or "").strip():
        return currency_for_business_group(plan.business_group)
    if profile and str(profile.business_group or "").strip():
        return currency_for_business_group(
            profile.business_group,
            profile.personal_currency,
        )
    if profile and str(profile.personal_currency or "").strip():
        return normalize_currency(profile.personal_currency)
    return normalize_currency(getattr(order, "currency", None))


def normalize_order_region_fields(data, profile=None):
    """
    Align business_group and currency on an order payload dict.

    Priority when business_group is blank:
      1. Map from explicit currency (USD → USA)
      2. Employee / plan profile (handled by derive_* on a temp object)
    """
    from .business_groups import normalize_business_group

    class _OrderStub:
        pass

    stub = _OrderStub()
    stub.business_group = str(data.get("business_group") or "").strip()
    stub.currency = str(data.get("currency") or "").strip()
    stub.employee_id = data.get("employee_id")
    stub.order_date = data.get("order_date")
    stub.position_name = data.get("position_name")
    stub.organization_id = data.get("organization_id")
    stub.organization = data.get("organization")

    group = derive_order_business_group(stub, profile=profile)
    currency = derive_order_currency(stub, profile=profile)

    if group:
        data["business_group"] = normalize_business_group(group, default="")
    if currency:
        data["currency"] = currency
    return data


def sync_order_region(order, profile=None, save=True):
    """Persist aligned business_group and currency on an order."""
    profile = profile or _get_user_profile_for_order(order)
    currency = derive_order_currency(order, profile=profile)
    business_group = derive_order_business_group(order, profile=profile)

    update_fields = []
    if currency and normalize_currency(getattr(order, "currency", None)) != currency:
        order.currency = currency
        update_fields.append("currency")
    if business_group and str(getattr(order, "business_group", None) or "").strip() != business_group:
        order.business_group = business_group
        update_fields.append("business_group")

    if save and update_fields:
        order.save(update_fields=update_fields)
    return {"currency": currency, "business_group": business_group}


def sync_order_currency(order, profile=None, save=True):
    """Backward-compatible alias — also sets business_group when missing."""
    result = sync_order_region(order, profile=profile, save=save)
    return result["currency"]


def _plan_queryset_for_order(order):
    from .tenants import allow_default_organization_fallback

    qs = CompensationPlan.objects.filter(status="Active")
    org_id = getattr(order, "organization_id", None)
    if org_id:
        qs = qs.filter(organization_id=org_id)
    elif allow_default_organization_fallback():
        qs = qs.filter(organization__isnull=True)
    else:
        return CompensationPlan.objects.none()
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


def _month_bounds_for_order(order):
    from .plan_periods import month_bounds

    order_date = getattr(order, "order_date", None)
    if not order_date:
        return None, None
    return month_bounds(order_date.year, order_date.month)


def _aggregate_currency_for_order(order):
    return normalize_currency(getattr(order, "currency", None))


def _eligible_orders_for_employee_month(order):
    if not order or not getattr(order, "employee_id", None) or not getattr(order, "order_date", None):
        return Order.objects.none()
    period_start, period_end = _month_bounds_for_order(order)
    qs = Order.objects.filter(
        employee_id=order.employee_id,
        order_date__gte=period_start,
        order_date__lte=period_end,
        order_status__iexact="Success",
        currency__iexact=_aggregate_currency_for_order(order),
    )
    org_id = getattr(order, "organization_id", None)
    if org_id:
        qs = qs.filter(organization_id=org_id)
    else:
        from .tenants import allow_default_organization_fallback

        if allow_default_organization_fallback():
            qs = qs.filter(organization__isnull=True)
        else:
            return Order.objects.none()
    return qs.order_by("order_date", "id")


def _aggregate_commission_queryset_for_order(order):
    period_start, _period_end = _month_bounds_for_order(order)
    if not period_start or not getattr(order, "employee_id", None):
        return Commission.objects.none()
    qs = Commission.objects.filter(
        calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH,
        period_start=period_start,
        currency__iexact=_aggregate_currency_for_order(order),
    ).filter(
        models.Q(employee__email__iexact=f"{order.employee_id}@company.com")
        | models.Q(sale__order__employee_id=order.employee_id)
    )
    org_id = getattr(order, "organization_id", None)
    if org_id:
        qs = qs.filter(organization_id=org_id)
    else:
        from .tenants import allow_default_organization_fallback

        if allow_default_organization_fallback():
            qs = qs.filter(organization__isnull=True)
        else:
            return Commission.objects.none()
    profile = _get_user_profile_for_order(order)
    if profile and profile.email:
        qs = qs | Commission.objects.filter(
            calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH,
            period_start=period_start,
            currency__iexact=_aggregate_currency_for_order(order),
            employee__email__iexact=profile.email,
            organization_id=org_id,
        )
    return qs.distinct()


def _aggregate_has_locked_commissions(order):
    return _aggregate_commission_queryset_for_order(order).filter(
        status__in=Commission.LOCKED_STATUSES
    ).exists()


from .workflow import order_has_locked_commissions


def _order_has_approved_commissions(order):
    return order_has_locked_commissions(order)


def _version_queryset_for_order(order):
    """Published plan versions visible to this order's org/territory."""
    qs = CommissionPlanVersion.objects.filter(
        status=CommissionPlanVersion.STATUS_PUBLISHED,
        compensation_plan__status="Active",
    ).select_related("compensation_plan")

    org_id = getattr(order, "organization_id", None)
    if org_id:
        qs = qs.filter(organization_id=org_id)
    else:
        from .tenants import allow_default_organization_fallback

        if allow_default_organization_fallback():
            qs = qs.filter(organization__isnull=True)
        else:
            return CommissionPlanVersion.objects.none()

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

    order_date = getattr(order, "order_date", None)
    if order_date:
        qs = qs.filter(effective_from__lte=order_date).filter(
            models.Q(effective_to__gte=order_date)
            | models.Q(effective_to__isnull=True)
        )
    return qs


def resolve_compensation_plan_version(order):
    """
    Resolve the Published plan version whose effective range contains the
    order date (effective_from <= order_date <= effective_to).

    Priority mirrors legacy plan resolution:
      1. Position-specific version (order.position_name, then profile)
      2. Role-based version (profile.role) — only versions without position_name

    Returns (version, lookup_source) or (None, None). Draft versions never match.
    """
    user_profile = _get_user_profile_for_order(order)
    empty_position = models.Q(position_name__isnull=True) | models.Q(position_name="")
    version_base = _version_queryset_for_order(order)
    ordering = ("-effective_from", "-version_number", "-id")

    for pos_name in _position_names_to_try(order, user_profile):
        version = (
            version_base.filter(position_name__iexact=pos_name)
            .exclude(position_name__isnull=True)
            .exclude(position_name="")
            .order_by(*ordering)
            .first()
        )
        if version:
            return version, f"position_name:{pos_name}"

    if user_profile and user_profile.role:
        role = str(user_profile.role).strip()
        if role:
            version = (
                version_base.filter(role__iexact=role)
                .filter(empty_position)
                .order_by(*ordering)
                .first()
            )
            if version:
                return version, f"role:{role}"

    return None, None


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
    date_label = order_date.strftime("%d %b %Y") if order_date else "that date"

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
                f"Position '{pos_name}' has compensation plan(s) but no Published "
                f"version covers {date_label}. Publish or extend a version’s "
                "effective date range."
            )

    if profile and profile.role:
        role = str(profile.role).strip()
        if role:
            role_plans = plan_base.filter(role__iexact=role).filter(empty_position)
            if role_plans.exists() and not role_plans.filter(effective).exists():
                return (
                    f"Role '{role}' has compensation plan(s) but no Published "
                    f"version covers {date_label}. Clone/publish a version whose "
                    f"effective range includes {date_label}."
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
                        f"User '{user_label}' has role '{role}' but no matching "
                        f"plan version for {date_label}. Active plans use role(s): "
                        f"{role_list}."
                    )
                return (
                    f"No Published plan version for role '{role}' on {date_label}. "
                    "Create a plan and publish Version 1 with an effective range "
                    "covering this date."
                )

    if not profile:
        return (
            f"No compensation plan matches position_name '{position}' "
            f"for order date {order_date}."
        )

    return (
        f"No Published plan version covers {date_label}. "
        "Check plan status, version status=Published, and effective_from/to."
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


def find_sc_lookup_tier(plan, order, sales_amount, version=None):
    """Best matching SC Lookup row for an order and sales amount."""
    source = version or plan
    if not source or source.commission_table_type != "LOOKUP" or not order:
        return None

    if version is not None:
        row_qs = SCLookupTable.objects.filter(plan_version=version, is_active=True)
    else:
        row_qs = SCLookupTable.objects.filter(compensation_plan=plan, is_active=True)

    candidates = []
    for row in row_qs.order_by("sequence", "id"):
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


def _rate_qs_for(plan, version):
    if version is not None:
        return SCRateTable.objects.filter(plan_version=version)
    return SCRateTable.objects.filter(compensation_plan=plan)


def _landing_tier_amount(rate_qs, sales_amount):
    """Commission for one amount: find the tier band the amount falls into
    and apply that tier's rate to the whole amount."""
    tier = (
        rate_qs.filter(
            is_active=True,
            from_amount__lte=sales_amount,
        )
        .filter(
            models.Q(to_amount__gte=sales_amount)
            | models.Q(to_amount__isnull=True)
        )
        .order_by("sequence")
        .first()
    )
    if not tier:
        return Decimal("0.00")
    return (sales_amount * tier.commission_rate / Decimal("100")) + tier.bonus_amount


def _marginal_band_upper(tiers, index):
    """Upper edge of band `index`. Returns None when the band is open-ended
    (the highest band is always treated as open-ended)."""
    if index >= len(tiers) - 1:
        return None
    upper = tiers[index].to_amount
    if upper is None:
        # A non-top band with no ceiling extends to the next band's floor.
        return tiers[index + 1].from_amount or Decimal("0")
    return upper


def _marginal_band_index_for_level(tiers, level):
    """Index of the band whose [from, upper) range contains `level`. The top
    band is open-ended, so any level at/above its floor lands there."""
    n = len(tiers)
    for index in range(n):
        lower = tiers[index].from_amount or Decimal("0")
        upper = _marginal_band_upper(tiers, index)
        if level < lower:
            return index
        if upper is None or level < upper:
            return index
    return n - 1


def _marginal_single_order(tiers, fill_level, amount):
    """Commission for ONE order under the fill model.

    The month's bands are filled sequentially by a running `fill_level`. For
    each order we top up the leftover room in the band the fill level currently
    sits in (at that band's rate), then charge the ENTIRE remainder of the
    order at the next band's rate — the remainder is not capped at the next
    band's width and never cascades further.

    Example (0-10k @ 5%, 10k-50k @ 10%, 50k-100k @ 15%):
      fill_level 9,000, order 50,000 -> 1,000 @ 5% + 49,000 @ 10%.
    """
    amount = Decimal(str(amount or "0"))
    if amount <= 0 or not tiers:
        return Decimal("0.00")

    index = _marginal_band_index_for_level(tiers, fill_level)
    current = tiers[index]
    upper = _marginal_band_upper(tiers, index)

    # Open-ended current band: the whole order earns the current rate.
    if upper is None:
        return (
            amount * current.commission_rate / Decimal("100")
            + (current.bonus_amount or Decimal("0.00"))
        )

    room = upper - fill_level
    if room < 0:
        room = Decimal("0.00")

    if amount <= room:
        return (
            amount * current.commission_rate / Decimal("100")
            + (current.bonus_amount or Decimal("0.00"))
        )

    nxt = tiers[index + 1] if index + 1 < len(tiers) else current
    remainder = amount - room
    total = room * current.commission_rate / Decimal("100")
    total += remainder * nxt.commission_rate / Decimal("100")
    total += nxt.bonus_amount or Decimal("0.00")
    return total


def _marginal_commission_per_order(plan, orders, version=None):
    """MARGINAL tables are calculated per order with a running fill level that
    carries across the month's orders (processed in chronological order). Each
    order tops up the current band's leftover at its rate, then the rest of the
    order is paid at the next band's rate. The monthly commission is the sum of
    the per-order commissions."""
    rate_qs = _rate_qs_for(plan, version)
    tiers = list(rate_qs.filter(is_active=True).order_by("from_amount", "sequence"))
    if not tiers:
        return Decimal("0.00")
    total = Decimal("0.00")
    fill_level = Decimal("0.00")
    for order in orders:
        amount = order.sales_amount or Decimal("0.00")
        if amount <= 0:
            continue
        total += _marginal_single_order(tiers, fill_level, amount)
        fill_level += amount
    return total


def _rate_commission_per_order(plan, orders, version=None):
    """RATE tables are calculated per order: each order's value picks the
    tier band it falls into, that tier's rate applies to the whole order
    amount, and the monthly commission is the sum of per-order commissions.

    Example (10k-50k @ 0.5%, 50k-100k @ 1%): orders of 15,000 and 55,000
    earn 75 + 550 = 625 — the orders are never added together first.
    """
    rate_qs = _rate_qs_for(plan, version)
    total = Decimal("0.00")
    for order in orders:
        amount = order.sales_amount or Decimal("0.00")
        total += _landing_tier_amount(rate_qs, amount)
    return total


def _calculate_amount_for_plan(plan, sales_amount, order=None, version=None):
    """Apply RATE, HIGHEST, FLAT, or LOOKUP table rules; returns Decimal commission or zero.

    When a plan version is given, only rows belonging to that immutable
    version are used; otherwise legacy plan-level rows apply.

    HIGHEST uses the same banded rate rows as RATE, but the caller should
    pass the monthly sales total so the matching tier rate applies to the
    entire aggregate (not per order).
    """
    commission_amount = Decimal("0.00")
    source = version or plan

    rate_qs = _rate_qs_for(plan, version)
    if version is not None:
        flat_qs = SCFlatRateTable.objects.filter(plan_version=version)
    else:
        flat_qs = SCFlatRateTable.objects.filter(compensation_plan=plan)

    if source.commission_table_type in ("RATE", "HIGHEST"):
        commission_amount = _landing_tier_amount(rate_qs, sales_amount)

    elif source.commission_table_type == "MARGINAL":
        tiers = list(
            rate_qs.filter(is_active=True).order_by("from_amount", "sequence")
        )
        commission_amount = _marginal_single_order(
            tiers, Decimal("0.00"), sales_amount
        )

    elif source.commission_table_type == "FLAT":
        flat = flat_qs.filter(
            is_active=True,
            minimum_sales_threshold__lte=sales_amount,
        ).first()
        if flat:
            commission_amount = (
                sales_amount * flat.flat_rate / Decimal("100")
            ) + flat.bonus_amount

    elif source.commission_table_type == "LOOKUP":
        tier = find_sc_lookup_tier(plan, order, sales_amount, version=version)
        if tier:
            commission_amount = (
                sales_amount * tier.commission_rate / Decimal("100")
            ) + tier.bonus_amount

    return commission_amount


def _get_or_create_employee_for_order(order, user_profile):
    org = getattr(order, "organization", None) or getattr(user_profile, "organization", None)
    if user_profile:
        employee, _ = Employee.objects.get_or_create(
            organization=org,
            email=user_profile.email,
            defaults={
                "name": user_profile.name or user_profile.employee_id,
            },
        )
        return employee

    employee, _ = Employee.objects.get_or_create(
        organization=org,
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
                organization=getattr(parent_user, "organization", None),
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
    Remove prior sale/commission rows for this order's employee-month group.

    Skips deletion when approved commissions exist unless force=True (admin recalc).
    """
    if not order or not order.pk:
        return 0
    if not force and _aggregate_has_locked_commissions(order):
        logger.warning(
            "Skipping commission recalc for order %s: locked monthly commission exists",
            order.order_id,
        )
        return 0
    eligible_orders = _eligible_orders_for_employee_month(order)
    order_sales = Sale.objects.filter(
        models.Q(order__in=eligible_orders) | models.Q(order=order)
    )
    summary_sale_ids = _aggregate_commission_queryset_for_order(order).values_list(
        "sale_id", flat=True
    )
    deleted_order_sales, _ = order_sales.delete()
    deleted_summary_sales, _ = Sale.objects.filter(id__in=summary_sale_ids).delete()
    return deleted_order_sales + deleted_summary_sales


def calculate_commission_for_order(order, replace_existing=True, force=False):
    """
    Calculate one monthly aggregate commission for this order's employee/month.

    Plan lookup priority:
      1. Active plan matching position_name (order, then user profile)
      2. Active role-based plan (no position_name on plan)

    Hierarchy:
      split_percentage = % of commission kept by the child; parent gets the rest.

    replace_existing: If True, delete existing commissions for this employee/month first.
    force: Allow replacing approved commissions (admin bulk recalc).
    """
    sync_order_region(order, save=True)

    if replace_existing:
        if not force and _aggregate_has_locked_commissions(order):
            logger.warning(
                "Commission calc skipped for order %s (locked monthly aggregate, use force recalc)",
                order.order_id,
            )
            return None
        clear_commissions_for_order(order, force=force)

    eligible_orders = _eligible_orders_for_employee_month(order)
    if not eligible_orders.exists():
        logger.info(
            "Commission calc skipped for order %s: no successful orders in employee month",
            order.order_id,
        )
        return None

    representative_order = eligible_orders.first()
    period_start, period_end = _month_bounds_for_order(representative_order)
    total_sales = sum(
        (row.sales_amount or Decimal("0.00")) for row in eligible_orders
    )
    source_order_count = eligible_orders.count()

    # Enterprise path: resolve the immutable Published version whose
    # effective range contains the order date. Legacy fallback covers
    # plans created before versioning (no version rows).
    plan_version, lookup_source = resolve_compensation_plan_version(
        representative_order
    )
    if plan_version:
        plan = plan_version.compensation_plan
    else:
        plan, lookup_source = resolve_compensation_plan(representative_order)
        if plan and plan.versions.exists():
            # Plan has versions but none Published for this date — versioned
            # plans must never calculate from mutable plan-level data.
            logger.warning(
                "Plan %s matched for order %s but has no Published version "
                "covering %s; skipping calculation.",
                plan.id,
                representative_order.order_id,
                representative_order.order_date,
            )
            plan = None

    if not plan:
        user_profile = _get_user_profile_for_order(representative_order)
        logger.warning(
            "No compensation plan for order %s "
            "(position_name=%s, employee_id=%s, profile_role=%s, sales_amount=%s, "
            "order_date=%s, organization_id=%s). %s",
            representative_order.order_id,
            representative_order.position_name,
            representative_order.employee_id,
            getattr(user_profile, "role", None),
            total_sales,
            representative_order.order_date,
            getattr(representative_order, "organization_id", None),
            explain_plan_resolution_failure(representative_order),
        )
        return None

    logger.info(
        "Plan matched for employee-month %s/%s: plan_id=%s version=%s lookup=%s type=%s",
        representative_order.employee_id,
        period_start,
        plan.id,
        getattr(plan_version, "version_number", None),
        lookup_source,
        (plan_version or plan).commission_table_type,
    )

    original_sales_amount = representative_order.sales_amount
    representative_order.sales_amount = total_sales
    table_type = (plan_version or plan).commission_table_type
    if table_type == "RATE":
        # RATE tables: each order picks the tier band its own value falls
        # into; the monthly commission is the sum of per-order commissions.
        commission_amount = _rate_commission_per_order(
            plan, eligible_orders, version=plan_version
        )
    elif table_type == "MARGINAL":
        # MARGINAL tables: a running fill level carries across the month's
        # orders. Each order tops up the current band's leftover at its rate,
        # then the rest of the order is paid at the next band's rate.
        commission_amount = _marginal_commission_per_order(
            plan, eligible_orders, version=plan_version
        )
    else:
        # HIGHEST / FLAT / LOOKUP: use the monthly sales total. HIGHEST
        # applies the matching tier rate to the entire monthly sum.
        commission_amount = _calculate_amount_for_plan(
            plan,
            total_sales,
            order=representative_order,
            version=plan_version,
        )
    if commission_amount <= 0:
        representative_order.sales_amount = original_sales_amount
        if plan_version is not None:
            from .plan_versions import _has_rate_configuration

            if not _has_rate_configuration(plan_version):
                logger.warning(
                    "No commission for %s/%s: matched Published version %s of "
                    "plan %s (id=%s) has no active %s rate rows. Rates added "
                    "later may be sitting on an unpublished Draft — publish "
                    "that draft (and archive the empty version) to fix.",
                    representative_order.employee_id,
                    period_start,
                    plan_version.version_number,
                    plan.plan_name,
                    plan.id,
                    plan_version.commission_table_type,
                )
                return None
        logger.warning(
            "No commission for %s/%s: no order matched a tier of plan %s "
            "(id=%s, version=%s, type=%s, monthly sales %s). Check that the "
            "rate table bands cover typical order values — the top tier "
            "usually needs an open-ended (blank) To Amount. Any previously "
            "calculated commission for this month was replaced with nothing.",
            representative_order.employee_id,
            period_start,
            plan.plan_name,
            plan.id,
            getattr(plan_version, "version_number", None),
            (plan_version or plan).commission_table_type,
            total_sales,
        )
        return None

    from .commission_rules import apply_commission_rules

    user_profile = _get_user_profile_for_order(representative_order)
    commission_amount, credit_amount, matched_rule, rule_meta = apply_commission_rules(
        plan, representative_order, user_profile, commission_amount,
        version=plan_version,
    )
    representative_order.sales_amount = original_sales_amount
    if commission_amount <= 0:
        return None

    employee = _get_or_create_employee_for_order(representative_order, user_profile)

    sale = Sale.objects.create(
        organization=getattr(representative_order, "organization", None),
        order=None,
        employee=employee,
        employee_salary=Decimal("0.00"),
        amount=total_sales,
    )

    employee_amount, parent_amount, parent_employee = _apply_hierarchy_split(
        representative_order, commission_amount
    )

    supporting_doc = None
    supporting_ver = None
    try:
        from .document_views import resolve_supporting_document_for_plan

        supporting_doc, supporting_ver = resolve_supporting_document_for_plan(
            plan, organization=getattr(representative_order, "organization", None)
        )
    except Exception:
        supporting_doc, supporting_ver = None, None

    commission = Commission.objects.create(
        organization=getattr(representative_order, "organization", None),
        employee=employee,
        sale=sale,
        commission_amount=employee_amount,
        compensation_plan=plan,
        plan_version=plan_version,
        commission_rule=matched_rule,
        credit_amount=credit_amount,
        result_classification=rule_meta.get("result_classification", ""),
        earning_group=rule_meta.get("earning_group", ""),
        hold_until=rule_meta.get("hold_until"),
        reason_code=rule_meta.get("reason_code", ""),
        rule_result_name=rule_meta.get("rule_result_name", ""),
        status=Commission.STATUS_CALCULATED,
        calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH,
        period_start=period_start,
        period_end=period_end,
        source_order_count=source_order_count,
        source_sales_total=total_sales,
        currency=_aggregate_currency_for_order(representative_order),
        supporting_document=supporting_doc,
        supporting_document_version=supporting_ver,
    )

    if parent_employee and parent_amount > 0:
        Commission.objects.create(
            organization=getattr(representative_order, "organization", None),
            employee=parent_employee,
            sale=sale,
            commission_amount=parent_amount,
            compensation_plan=plan,
            plan_version=plan_version,
            status=Commission.STATUS_CALCULATED,
            calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH,
            period_start=period_start,
            period_end=period_end,
            source_order_count=source_order_count,
            source_sales_total=total_sales,
            currency=_aggregate_currency_for_order(representative_order),
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

        orders = orders.filter(
            order_employee_search_q(employee_q, organization=organization)
        )
    orders = orders.order_by("order_date", "order_id")
    stats = {
        "processed": 0,
        "skipped_approved": 0,
        "failed": 0,
        "employee_q": employee_q,
        "scoped": bool(employee_q),
        "order_count": orders.count(),
    }
    seen_groups = set()
    for order in orders:
        period_start, _period_end = _month_bounds_for_order(order)
        group_key = (
            getattr(order, "organization_id", None),
            order.employee_id,
            period_start,
            _aggregate_currency_for_order(order),
        )
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)
        if not force and _aggregate_has_locked_commissions(order):
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
