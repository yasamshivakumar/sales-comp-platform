"""Scope querysets to the logged-in rep without ambiguous substring matches."""

from django.db.models import Q


def profile_commission_q(profile, login_email=None):
    """
    Build a Q filter for one rep's commissions.


    """
    emails = set()
    if login_email:
        emails.add(str(login_email).strip().lower())
    if profile:
        if profile.email:
            emails.add(profile.email.strip().lower())
        if profile.employee_id:
            employee_id = profile.employee_id.strip()
            emails.add(f"{employee_id}@company.com".lower())
            emails.add(f"{employee_id}@gmail.com".lower())

    if not emails and not (profile and profile.employee_id):
        return Q(pk__in=[])

    query = Q()
    for email in emails:
        query |= Q(employee__email__iexact=email)

    if profile and profile.employee_id:
        query |= Q(sale__order__employee_id=profile.employee_id)

    return query
