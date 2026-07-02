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


def resolve_crm_owner_to_employee_id(organization, crm_owner_id, integration=None):
    """Map a CRM owner/user id to the Incentra employee_id."""
    owner_id = str(crm_owner_id or "").strip()
    if not owner_id or not organization:
        return None

    profile = UserProfile.objects.filter(
        organization=organization,
        crm_user_id=owner_id,
    ).first()
    if not profile:
        profile = UserProfile.objects.filter(
            organization=organization,
            crm_alt_user_id=owner_id,
        ).first()

    if profile and profile.employee_id:
        return profile.employee_id

    if integration and integration.provider == "hubspot":
        from .registry import get_connector

        connector = get_connector(integration)
        owner = connector.fetch_owner(owner_id) if hasattr(connector, "fetch_owner") else None
        if owner:
            email = str(owner.get("email") or "").strip().lower()
            hubspot_owner_id = str(owner.get("id") or owner_id).strip()
            hubspot_user_id = str(owner.get("userId") or "").strip()
            if email:
                profile = UserProfile.objects.filter(
                    organization=organization,
                    email__iexact=email,
                ).first()
                if profile and profile.employee_id:
                    updates = {}
                    if hubspot_owner_id and profile.crm_user_id != hubspot_owner_id:
                        updates["crm_user_id"] = hubspot_owner_id
                    if hubspot_user_id and profile.crm_alt_user_id != hubspot_user_id:
                        updates["crm_alt_user_id"] = hubspot_user_id
                    if updates:
                        profile.save(update_fields=list(updates.keys()))
                    return profile.employee_id

    return None
