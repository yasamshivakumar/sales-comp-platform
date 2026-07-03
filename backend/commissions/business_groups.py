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
_CURRENCY_TO_BUSINESS_GROUP = {item["currency"]: item["value"] for item in BUSINESS_GROUPS}

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


def business_group_for_currency(currency_code):
    """Map ISO currency to a known business group (USD → USA, INR → India, …)."""
    code = normalize_currency(currency_code, default="")
    if not code:
        return ""
    return _CURRENCY_TO_BUSINESS_GROUP.get(code, "")


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
            user_profile.business_group if user_profile else "",
            default="",
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


def _other_group_currencies(group):
    normalized = normalize_business_group(group, default="")
    return [
        item["currency"]
        for item in BUSINESS_GROUPS
        if item["value"] != normalized
    ]


def _blank_business_group_q(prefix=""):
    if prefix:
        return Q(**{f"{prefix}__business_group": ""}) | Q(
            **{f"{prefix}__business_group__isnull": True}
        )
    return Q(business_group="") | Q(business_group__isnull=True)


def _profile_employee_ids_for_group(group, organization=None):
    from .models import UserProfile

    profiles = UserProfile.objects.filter(business_group__iexact=group)
    if organization is not None:
        profiles = profiles.filter(organization=organization)
    return list(profiles.exclude(employee_id="").values_list("employee_id", flat=True))


def _profile_emails_for_group(group, organization=None):
    from .models import UserProfile

    profiles = UserProfile.objects.filter(business_group__iexact=group)
    if organization is not None:
        profiles = profiles.filter(organization=organization)
    return list(profiles.exclude(email="").values_list("email", flat=True))


def _implicit_business_group_q(group, group_currency, employee_ids, prefix=""):
    """
    Match rows without an explicit business_group.

    Prefer order/commission currency; fall back to employee profile only when
    currency is blank or matches the group's currency (not another region).
    """
    if not group_currency and not employee_ids:
        return Q(pk__in=[])

    blank = _blank_business_group_q(prefix)
    currency_field = f"{prefix}__currency" if prefix else "currency"
    employee_field = f"{prefix}__employee_id" if prefix else "employee_id"

    match = Q(pk__in=[])
    if group_currency:
        match |= Q(**{f"{currency_field}__iexact": group_currency})

    if employee_ids:
        employee_q = Q(**{f"{employee_field}__in": employee_ids})
        for other_currency in _other_group_currencies(group):
            employee_q &= ~Q(**{f"{currency_field}__iexact": other_currency})
        employee_q &= (
            Q(**{f"{currency_field}": ""})
            | Q(**{f"{currency_field}__isnull": True})
            | Q(**{f"{currency_field}__iexact": group_currency})
        )
        match |= employee_q

    return blank & match


def _commission_row_group_q(group, group_currency, emails):
    """Monthly aggregate commissions (sale.order is null) — use currency + profile."""
    from .models import Commission

    monthly = Q(calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH) | Q(
        sale__order__isnull=True
    )

    match = Q(pk__in=[])
    if group_currency:
        match |= Q(currency__iexact=group_currency)

    if emails:
        email_q = Q(employee__email__in=emails)
        for other_currency in _other_group_currencies(group):
            email_q &= ~Q(currency__iexact=other_currency)
        email_q &= Q(currency="") | Q(currency__iexact=group_currency)
        match |= email_q

    return monthly & match


def order_business_group_q(business_group, organization=None):
    group = normalize_business_group(business_group, default="")
    if not group:
        return Q()

    group_currency = currency_for_business_group(group, None)
    employee_ids = _profile_employee_ids_for_group(group, organization)

    explicit = Q(business_group__iexact=group)
    implicit = _implicit_business_group_q(group, group_currency, employee_ids)
    return explicit | implicit


def commission_business_group_q(business_group, organization=None):
    group = normalize_business_group(business_group, default="")
    if not group:
        return Q()

    group_currency = currency_for_business_group(group, None)
    employee_ids = _profile_employee_ids_for_group(group, organization)
    emails = _profile_emails_for_group(group, organization)

    order_linked = Q(sale__order__isnull=False)
    order_explicit = order_linked & Q(sale__order__business_group__iexact=group)
    order_implicit = order_linked & _implicit_business_group_q(
        group,
        group_currency,
        employee_ids,
        prefix="sale__order",
    )
    commission_row = _commission_row_group_q(group, group_currency, emails)

    return order_explicit | order_implicit | commission_row


def apply_business_group_to_commissions(queryset, business_group, organization=None):
    if not business_group:
        return queryset
    return queryset.filter(commission_business_group_q(business_group, organization))


def apply_business_group_to_orders(queryset, business_group, organization=None):
    if not business_group:
        return queryset
    return queryset.filter(order_business_group_q(business_group, organization))


def commission_totals_by_business_group(
    queryset,
    *,
    amount_field="commission_amount",
    organization=None,
):
    from django.db.models import Sum

    results = []
    for item in BUSINESS_GROUPS:
        scoped = apply_business_group_to_commissions(
            queryset,
            item["value"],
            organization=organization,
        )
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


def sales_totals_by_business_group(queryset, organization=None):
    from django.db.models import Sum

    results = []
    for item in BUSINESS_GROUPS:
        scoped = apply_business_group_to_orders(
            queryset,
            item["value"],
            organization=organization,
        )
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
