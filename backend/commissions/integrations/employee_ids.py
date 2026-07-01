"""Allocate Incentra employee IDs for CRM-imported users."""

from ..models import UserProfile


def allocate_employee_id(organization):
    """Generate the next sequential employee id for an organization."""
    org_pk = organization.pk if organization else 0
    prefix = f"INC{org_pk:04d}-"
    existing_ids = UserProfile.objects.filter(
        organization=organization,
        employee_id__startswith=prefix,
    ).values_list("employee_id", flat=True)
    max_num = 0
    for employee_id in existing_ids:
        suffix = employee_id.rsplit("-", 1)[-1]
        try:
            max_num = max(max_num, int(suffix))
        except ValueError:
            continue
    return f"{prefix}{max_num + 1:05d}"


def resolve_crm_owner_to_employee_id(organization, crm_owner_id):
    """Map a CRM owner/user id to the Incentra employee_id."""
    if not crm_owner_id:
        return None
    profile = UserProfile.objects.filter(
        organization=organization,
        crm_user_id=str(crm_owner_id).strip(),
    ).first()
    if profile and profile.employee_id:
        return profile.employee_id
    return None
