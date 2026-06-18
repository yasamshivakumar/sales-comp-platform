"""Business group definitions and region → currency mapping."""

from django.db.models import Q

from .currencies import DEFAULT_CURRENCY, normalize_currency

BUSINESS_GROUPS = [
    {"value": "India", "label": "India", "currency": "INR"},
    {"value": "USA", "label": "USA", "currency": "USD"},
    {"value": "Australia", "label": "Australia", "currency": "AUD"},
    {"value": "Europe", "label": "Europe", "currency": "EUR"},
]

_BUSINESS_GROUP_BY_VALUE = {item["value"]: item for item in BUSINESS_GROUPS}

_ALIASES = {
    "india": "India",
    "usa": "USA",
    "us": "USA",
    "u.s.": "USA",
    "u.s.a.": "USA",
    "united states": "USA",
    "america": "USA",
    "australia": "Australia",
    "au": "Australia",
    "aus": "Australia",
    "europe": "Europe",
    "eu": "Europe",
    "emea": "Europe",
}


def business_group_choices_for_api():
    return [{"value": item["value"], "label": item["label"]} for item in BUSINESS_GROUPS]


def normalize_business_group(value, default="India"):
    raw = str(value or "").strip()
    if not raw:
        return default
    if raw in _BUSINESS_GROUP_BY_VALUE:
        return raw
    alias = _ALIASES.get(raw.lower())
    if alias:
        return alias
    for item in BUSINESS_GROUPS:
        if item["value"].lower() == raw.lower():
            return item["value"]
    return raw


def currency_for_business_group(business_group, personal_currency=None):
    normalized = normalize_business_group(business_group, default="")
    item = _BUSINESS_GROUP_BY_VALUE.get(normalized)
    if item:
        return item["currency"]
    return normalize_currency(personal_currency, DEFAULT_CURRENCY)


def list_business_groups_for_org(org=None):
    from .models import UserProfile

    qs = UserProfile.objects.exclude(business_group="").exclude(
        business_group__isnull=True
    )
    if org is not None:
        qs = qs.filter(organization=org)
    seen = set()
    groups = []
    for raw in qs.values_list("business_group", flat=True).distinct():
        normalized = normalize_business_group(raw, default="")
        if normalized and normalized not in seen:
            seen.add(normalized)
            groups.append(normalized)
    for item in BUSINESS_GROUPS:
        if item["value"] not in seen:
            groups.append(item["value"])
    return sorted(set(groups), key=lambda value: value.lower())


def resolve_dashboard_business_group(request, user_profile, can_view_all_groups):
    """
    Determine effective business-group filter for dashboard reports.

    Reps and managers are scoped to their profile business group.
    Admins/finance may pass ?business_group=USA or ?business_group=all.
    """
    param = (request.query_params.get("business_group") or "").strip()
    org = getattr(request, "organization", None)
    available = list_business_groups_for_org(org)

    if not can_view_all_groups:
        profile_group = normalize_business_group(
            user_profile.business_group if user_profile else ""
        )
        if profile_group not in available:
            available = sorted(set(available + [profile_group]), key=str.lower)
        return profile_group, False, available

    if not param or param.lower() == "all":
        return None, True, available

    selected = normalize_business_group(param)
    if selected not in available:
        available = sorted(set(available + [selected]), key=str.lower)
    return selected, False, available


def commission_business_group_q(business_group):
    from .models import UserProfile

    group = normalize_business_group(business_group, default="")
    if not group:
        return Q()

    employee_ids = UserProfile.objects.filter(
        business_group__iexact=group
    ).exclude(employee_id="").values_list("employee_id", flat=True)

    return Q(sale__order__business_group__iexact=group) | Q(
        sale__order__employee_id__in=employee_ids
    )


def order_business_group_q(business_group):
    from .models import UserProfile

    group = normalize_business_group(business_group, default="")
    if not group:
        return Q()

    employee_ids = UserProfile.objects.filter(
        business_group__iexact=group
    ).exclude(employee_id="").values_list("employee_id", flat=True)

    return Q(business_group__iexact=group) | Q(employee_id__in=employee_ids)


def apply_business_group_to_commissions(queryset, business_group):
    if not business_group:
        return queryset
    return queryset.filter(commission_business_group_q(business_group))


def apply_business_group_to_orders(queryset, business_group):
    if not business_group:
        return queryset
    return queryset.filter(order_business_group_q(business_group))


def commission_totals_by_business_group(queryset, *, amount_field="commission_amount"):
    from django.db.models import Sum

    results = []
    for item in BUSINESS_GROUPS:
        scoped = apply_business_group_to_commissions(queryset, item["value"])
        total = scoped.aggregate(total=Sum(amount_field))["total"] or 0
        count = scoped.count()
        if not total and not count:
            continue
        results.append(
            {
                "business_group": item["value"],
                "label": item["label"],
                "currency": item["currency"],
                "total": float(total),
                "count": count,
            }
        )
    return results


def sales_totals_by_business_group(queryset):
    from django.db.models import Sum

    results = []
    for item in BUSINESS_GROUPS:
        scoped = apply_business_group_to_orders(queryset, item["value"])
        total = scoped.aggregate(total=Sum("sales_amount"))["total"] or 0
        count = scoped.count()
        if not total and not count:
            continue
        results.append(
            {
                "business_group": item["value"],
                "label": item["label"],
                "currency": item["currency"],
                "total": float(total),
                "count": count,
            }
        )
    return results
