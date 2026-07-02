"""Allocate Incentra employee IDs for CRM-imported users."""

import logging

from django.db.models import Q

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


def normalize_hubspot_id(value):
    """Normalize HubSpot numeric ids that may arrive as strings or floats."""
    text = str(value or "").strip()
    if not text:
        return ""
    if "." in text:
        text = text.split(".", 1)[0]
    return text


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
        owner_id = normalize_hubspot_id(owner.get("id"))
        user_id = normalize_hubspot_id(owner.get("userId"))
        if owner_id:
            index[owner_id] = owner
        if user_id:
            index[user_id] = owner
    return index


def repair_hubspot_profile_mappings(organization, owner_index):
    """Align stored CRM ids on profiles with HubSpot owner id / userId pairs."""
    if not owner_index:
        return

    profiles = UserProfile.objects.all()
    if organization:
        profiles = profiles.filter(Q(organization=organization) | Q(organization__isnull=True))

    for profile in profiles.iterator():
        stored_ids = {
            normalize_hubspot_id(profile.crm_user_id),
            normalize_hubspot_id(profile.crm_alt_user_id),
        }
        stored_ids.discard("")
        for stored in stored_ids:
            meta = owner_index.get(stored)
            if not meta:
                continue
            _apply_hubspot_owner_ids(
                profile,
                normalize_hubspot_id(meta.get("id")),
                normalize_hubspot_id(meta.get("userId")),
            )


def _org_profile_queryset(organization):
    qs = UserProfile.objects.all()
    if organization:
        return qs.filter(Q(organization=organization) | Q(organization__isnull=True))
    return qs


def _find_profile(organization, **filters):
    """Find profiles in the integration org, including legacy rows without organization."""
    return _org_profile_queryset(organization).filter(**filters).first()


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


def _ensure_profile_employee_id(profile, organization):
    """Orders require employee_id; allocate one for login-only or admin profiles."""
    if not profile:
        return None
    if str(profile.employee_id or "").strip():
        return profile.employee_id
    org = organization or profile.organization
    profile.employee_id = allocate_employee_id(org)
    profile.save(update_fields=["employee_id"])
    return profile.employee_id


def _find_profile_by_email(organization, email):
    if not email:
        return None
    profile = _find_profile(organization, email__iexact=email)
    if profile:
        return profile
    return UserProfile.objects.filter(email__iexact=email).first()


def _owner_row_from_meta(owner_meta):
    owner_id = normalize_hubspot_id(owner_meta.get("id"))
    user_id = normalize_hubspot_id(owner_meta.get("userId"))
    email = str(owner_meta.get("email") or "").strip().lower()
    if not email and owner_id:
        email = f"hubspot-owner-{owner_id}@crm.import"
    return {
        "email": email,
        "name": owner_meta.get("full_name") or email,
        "first_name": owner_meta.get("firstName", ""),
        "last_name": owner_meta.get("lastName", ""),
        "crm_user_id": owner_id,
        "crm_alt_user_id": user_id,
        "role": "Sales Rep",
    }


def _import_hubspot_owner_row(organization, owner_meta):
    from .user_import import process_users_rows

    row = _owner_row_from_meta(owner_meta)
    return process_users_rows(organization, [row])


def _resolve_from_owner_meta(organization, owner_meta, *, auto_import=False):
    """Match an Incentra profile from HubSpot owner metadata."""
    if not owner_meta:
        return None

    hubspot_owner_id = normalize_hubspot_id(owner_meta.get("id"))
    hubspot_user_id = normalize_hubspot_id(owner_meta.get("userId"))
    email = str(owner_meta.get("email") or "").strip().lower()
    full_name = str(owner_meta.get("full_name") or "").strip()
    first_name = str(owner_meta.get("firstName") or "").strip()
    last_name = str(owner_meta.get("lastName") or "").strip()

    profile = None
    for lookup_id in (hubspot_user_id, hubspot_owner_id):
        if not lookup_id:
            continue
        profile = _find_profile(organization, crm_user_id=lookup_id)
        if not profile:
            profile = _find_profile(organization, crm_alt_user_id=lookup_id)
        if profile:
            break

    if not profile and email:
        profile = _find_profile_by_email(organization, email)

    if not profile and email and email.endswith("@crm.import"):
        local = email.split("@", 1)[0]
        if local.startswith("hubspot-owner-"):
            owner_hint = local.replace("hubspot-owner-", "", 1)
            profile = _find_profile(organization, crm_user_id=owner_hint)

    if not profile and full_name:
        profile = _find_profile(organization, name__iexact=full_name)

    if not profile and first_name and last_name:
        profile = _org_profile_queryset(organization).filter(
            first_name__iexact=first_name,
            last_name__iexact=last_name,
        ).first()

    if not profile and auto_import:
        result = _import_hubspot_owner_row(organization, owner_meta)
        if result.get("success"):
            profile = _find_profile_by_email(organization, email)
            if not profile and hubspot_owner_id:
                profile = _find_profile(organization, crm_user_id=hubspot_owner_id)

    if profile:
        if organization and not profile.organization_id:
            profile.organization = organization
            profile.save(update_fields=["organization"])
        _apply_hubspot_owner_ids(profile, hubspot_owner_id, hubspot_user_id)
        return _ensure_profile_employee_id(profile, organization)
    return None


def _lookup_owner_meta(owner_id, integration, owner_index):
    owner_meta = (owner_index or {}).get(owner_id) if owner_index else None
    if owner_meta:
        return owner_meta
    if integration and integration.provider == "hubspot":
        from .registry import get_connector

        connector = get_connector(integration)
        if hasattr(connector, "fetch_owner"):
            owner_meta = connector.fetch_owner(owner_id, for_resolution=True)
            if owner_meta:
                return owner_meta
    return None


def resolve_crm_owner_to_employee_id(
    organization,
    crm_owner_id,
    integration=None,
    owner_index=None,
    *,
    auto_import=False,
):
    """Map a CRM owner/user id to the Incentra employee_id."""
    owner_id = normalize_hubspot_id(crm_owner_id)
    if not owner_id:
        return None

    profile = _find_profile(organization, crm_user_id=owner_id)
    if not profile:
        profile = _find_profile(organization, crm_alt_user_id=owner_id)
    if profile:
        return _ensure_profile_employee_id(profile, organization)

    owner_meta = _lookup_owner_meta(owner_id, integration, owner_index)
    employee_id = _resolve_from_owner_meta(
        organization,
        owner_meta,
        auto_import=False,
    )
    if employee_id:
        return employee_id

    if auto_import and owner_meta:
        return _resolve_from_owner_meta(
            organization,
            owner_meta,
            auto_import=True,
        )

    return None


def resolve_error_hint(owner_id, integration, owner_index):
    """Build a short diagnostic hint for unresolved HubSpot owner ids."""
    meta = _lookup_owner_meta(owner_id, integration, owner_index)
    if not meta:
        return (
            " HubSpot owner was not found (active or archived). "
            "Ensure the deal owner email matches an Incentra employee, "
            "or reassign the deal in HubSpot to an active owner."
        )
    email = meta.get("email") or ""
    user_id = normalize_hubspot_id(meta.get("userId"))
    owner_id = normalize_hubspot_id(meta.get("id"))
    archived_note = " (archived in HubSpot)" if meta.get("archived") else ""
    profile = _find_profile_by_email(None, str(email).strip().lower()) if email else None
    if profile and not str(profile.employee_id or "").strip():
        return (
            f" HubSpot owner email={email or 'n/a'}, ownerId={owner_id or 'n/a'}{archived_note}. "
            f"Found Incentra profile for {email} but it has no employee id yet; retry after deploy."
        )
    if profile:
        return (
            f" HubSpot owner email={email or 'n/a'}, ownerId={owner_id or 'n/a'}{archived_note}. "
            f"Matched {email} but could not assign an employee id."
        )
    return (
        f" HubSpot owner email={email or 'n/a'}, ownerId={owner_id or 'n/a'}, "
        f"userId={user_id or 'n/a'}{archived_note}. "
        "Add this email in User Setup or reassign the deal to an active HubSpot owner."
    )
