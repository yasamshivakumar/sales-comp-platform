"""Default list limits and employee search for admin UIs."""

from django.db.models import Q

DEFAULT_EMPLOYEE_LIST_LIMIT = 50
MAX_EMPLOYEE_SEARCH_LIMIT = 100


def list_limit_for_request(request, *, searching: bool) -> int:
    raw = request.query_params.get("limit")
    if raw:
        try:
            return min(int(raw), MAX_EMPLOYEE_SEARCH_LIMIT)
        except (TypeError, ValueError):
            pass
    return MAX_EMPLOYEE_SEARCH_LIMIT if searching else DEFAULT_EMPLOYEE_LIST_LIMIT


def profile_search_q(term: str) -> Q:
    term = (term or "").strip()
    if not term:
        return Q()
    return (
        Q(employee_id__icontains=term)
        | Q(name__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(email__icontains=term)
        | Q(username__icontains=term)
        | Q(position_name__icontains=term)
    )


def commission_employee_search_q(term: str, organization=None) -> Q:
    term = (term or "").strip()
    if not term:
        return Q()
    from .models import UserProfile

    profiles = UserProfile.objects.filter(profile_search_q(term))
    if organization is not None:
        profiles = profiles.filter(organization=organization)
    profile_emails = list(profiles.values_list("email", flat=True))
    profile_employee_ids = list(
        profiles.exclude(employee_id="")
        .exclude(employee_id__isnull=True)
        .values_list("employee_id", flat=True)
    )
    # Legacy employee rows sometimes use "{employee_id}@company.com" instead
    # of the User Setup email; monthly aggregate commissions also have no
    # sale.order, so match those synthetic emails and profile employee IDs.
    synthetic_emails = [
        f"{eid}@company.com" for eid in profile_employee_ids if eid
    ]
    q = (
        Q(employee__name__icontains=term)
        | Q(employee__email__icontains=term)
        | Q(employee__email__in=profile_emails)
        | Q(employee__email__in=synthetic_emails)
        | Q(sale__order__order_id__icontains=term)
        | Q(sale__order__employee_id__icontains=term)
        | Q(sale__order__employee_id__in=profile_employee_ids)
    )
    if term.isdigit():
        q = q | Q(pk=int(term))
    return q


def order_employee_search_q(term: str, organization=None) -> Q:
    """Filter orders by employee_id or matching User Setup profile."""
    term = (term or "").strip()
    if not term:
        return Q()
    from .models import UserProfile

    profiles = UserProfile.objects.filter(profile_search_q(term))
    if organization is not None:
        profiles = profiles.filter(organization=organization)
    profile_employee_ids = profiles.exclude(
        employee_id=""
    ).values_list("employee_id", flat=True)
    return Q(employee_id__icontains=term) | Q(employee_id__in=profile_employee_ids)


def order_search_q(term: str) -> Q:
    """Search orders by ID, employee, product, service, distribution, etc."""
    term = (term or "").strip()
    if not term:
        return Q()
    return (
        Q(order_id__icontains=term)
        | Q(employee_id__icontains=term)
        | Q(product_name__icontains=term)
        | Q(service_name__icontains=term)
        | Q(distribution__icontains=term)
        | Q(position_name__icontains=term)
        | Q(region__icontains=term)
        | Q(customer_segment__icontains=term)
        | Q(business_group__icontains=term)
    )
