"""Allocate Incentra employee IDs for CRM-imported users."""

import logging

from ..models import UserProfile

logger = logging.getLogger("commissions")


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


def build_hubspot_owner_index(integration):
    """Map HubSpot owner id and userId to owner metadata for deal resolution."""
    if not integration or integration.provider != "hubspot":
        return {}
    from .registry import get_connector

    try:
        connector = get_connector(integration)
        owners = connector.fetch_records("users")
    except Exception:
        logger.exception("Failed to build HubSpot owner index for integration %s", integration.pk)
        return {}

    index = {}
    for owner in owners:
        owner_id = str(owner.get("id") or "").strip()
        user_id = str(owner.get("userId") or "").strip()
        if owner_id:
            index[owner_id] = owner
        if user_id:
            index[user_id] = owner
    return index


def _find_profile(organization, **filters):
    """Prefer org-scoped profiles, then fall back to legacy rows without organization."""
    qs = UserProfile.objects.filter(**filters)
    if organization:
        profile = qs.filter(organization=organization).first()
        if profile:
            return profile
    return qs.first()


def _apply_hubspot_owner_ids(profile, hubspot_owner_id, hubspot_user_id):
    updates = {}
    if hubspot_owner_id and profile.crm_user_id != hubspot_owner_id:
        updates["crm_user_id"] = hubspot_owner_id
    if hubspot_user_id and profile.crm_alt_user_id != hubspot_user_id:
        updates["crm_alt_user_id"] = hubspot_user_id
    if updates:
        profile.save(update_fields=list(updates.keys()))
    return profile


def _profile_employee_id(profile):
    if profile and profile.employee_id:
        return profile.employee_id
    return None


def _resolve_from_owner_meta(organization, owner_meta):
    """Match an Incentra profile from HubSpot owner metadata."""
    if not owner_meta:
        return None

    hubspot_owner_id = str(owner_meta.get("id") or "").strip()
    hubspot_user_id = str(owner_meta.get("userId") or "").strip()
    email = str(owner_meta.get("email") or "").strip().lower()

    profile = None
    if hubspot_user_id:
        profile = _find_profile(organization, crm_user_id=hubspot_user_id)
        if not profile:
            profile = _find_profile(organization, crm_alt_user_id=hubspot_user_id)

    if not profile and hubspot_owner_id:
        profile = _find_profile(organization, crm_user_id=hubspot_owner_id)
        if not profile:
            profile = _find_profile(organization, crm_alt_user_id=hubspot_owner_id)

    if not profile and email:
        profile = _find_profile(organization, email__iexact=email)

    if profile:
        _apply_hubspot_owner_ids(profile, hubspot_owner_id, hubspot_user_id)
        return _profile_employee_id(profile)
    return None


def resolve_crm_owner_to_employee_id(
    organization,
    crm_owner_id,
    integration=None,
    owner_index=None,
):
    """Map a CRM owner/user id to the Incentra employee_id."""
    owner_id = str(crm_owner_id or "").strip()
    if not owner_id:
        return None

    profile = _find_profile(organization, crm_user_id=owner_id)
    if not profile:
        profile = _find_profile(organization, crm_alt_user_id=owner_id)
    employee_id = _profile_employee_id(profile)
    if employee_id:
        return employee_id

    owner_meta = (owner_index or {}).get(owner_id) if owner_index else None
    if not owner_meta and integration and integration.provider == "hubspot":
        from .registry import get_connector

        connector = get_connector(integration)
        if hasattr(connector, "fetch_owner"):
            owner_meta = connector.fetch_owner(owner_id)

    return _resolve_from_owner_meta(organization, owner_meta)
