"""Import user rows from CRM sync (same column shape as User Setup CSV)."""

import logging
from datetime import datetime

from ..business_groups import currency_for_business_group
from ..currencies import normalize_currency
from ..models import HierarchyRelationship, Territory, UserProfile
from .employee_ids import allocate_employee_id

logger = logging.getLogger("commissions")


def _parse_hire_date(value):
    if value in ("", None):
        return None
    if hasattr(value, "isoformat"):
        return value
    text = str(value).strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid hire_date format: {text}")


def process_users_rows(organization, rows, *, allow_updates=True):
    """
    Import UserProfile rows from dicts (CSV / CRM column names).
    Returns {success, failed, errors, total_rows}.
    """
    success = 0
    failed = 0
    errors = []
    email_to_profile = {}
    username_to_profile = {}
    employee_id_to_profile = {}

    for index, row in enumerate(rows, start=1):
        try:
            email = str(row.get("email", "")).strip().lower()
            if not email:
                raise ValueError("email is required")

            role_val = str(row.get("role", "Sales Rep")).strip() or "Sales Rep"
            employee_id_val = str(row.get("employee_id", "")).strip()
            crm_user_id_val = str(row.get("crm_user_id", "")).strip()
            name_val = str(row.get("name", "")).strip()

            if crm_user_id_val and organization:
                existing_by_crm = UserProfile.objects.filter(
                    organization=organization,
                    crm_user_id=crm_user_id_val,
                ).first()
                if not existing_by_crm:
                    existing_by_crm = UserProfile.objects.filter(
                        organization=organization,
                        email__iexact=email,
                    ).first()
                if existing_by_crm and not employee_id_val:
                    employee_id_val = existing_by_crm.employee_id

            if not employee_id_val:
                employee_id_val = allocate_employee_id(organization)
            if not name_val:
                raise ValueError("name is required")

            enable_login = str(row.get("enable_login", "False")).strip().lower() in (
                "true",
                "1",
                "yes",
            )

            personal_target = row.get("personal_target", 0) or 0
            personal_target = float(personal_target)
            split_percentage = row.get("split_percentage", 100) or 100
            split_percentage = float(split_percentage)

            hire_date = _parse_hire_date(row.get("hire_date", ""))
            username = str(row.get("username", "")).strip() or email
            business_group = str(row.get("business_group", "India")).strip()
            raw_currency = str(row.get("personal_currency", "")).strip()
            personal_currency = (
                normalize_currency(raw_currency)
                if raw_currency
                else currency_for_business_group(business_group)
            )

            profile_lookup = {}
            if crm_user_id_val and organization:
                profile_lookup = {
                    "organization": organization,
                    "crm_user_id": crm_user_id_val,
                }
            else:
                profile_lookup = {"email": email}
                if organization:
                    profile_lookup["organization"] = organization

            territory_id = row.get("territory") or row.get("territory_id")
            defaults = {
                "organization": organization,
                "enable_login": enable_login,
                "name": name_val,
                "role": role_val,
                "username": username,
                "first_name": str(row.get("first_name", "")).strip(),
                "last_name": str(row.get("last_name", "")).strip(),
                "prefix": str(row.get("prefix", "")).strip(),
                "employee_id": employee_id_val,
                "crm_user_id": crm_user_id_val,
                "hire_date": hire_date,
                "personal_target": personal_target,
                "personal_currency": personal_currency,
                "business_group": business_group,
                "title": str(row.get("title", "")).strip(),
                "pay_period_type": str(row.get("pay_period_type", "Monthly")).strip(),
                "position_name": str(row.get("position_name", "")).strip(),
                "position_title": str(row.get("position_title", "")).strip(),
            }
            if territory_id:
                if not Territory.objects.filter(
                    pk=territory_id,
                    organization=organization,
                ).exists():
                    raise ValueError(
                        "Territory does not belong to this organization."
                    )
                defaults["territory_id"] = territory_id

            if enable_login and UserProfile.objects.filter(
                email__iexact=email,
            ).exclude(organization=organization).exists():
                raise ValueError(
                    "Login email is already used in another organization."
                )

            if allow_updates:
                profile, _created = UserProfile.objects.update_or_create(
                    **profile_lookup,
                    defaults=defaults,
                )
            else:
                from ..field_rules import find_user_profile_duplicates

                dup_errors = find_user_profile_duplicates(
                    organization,
                    email,
                    employee_id_val,
                )
                if dup_errors:
                    raise ValueError(" ".join(dup_errors))
                profile = UserProfile.objects.create(email=email, **defaults)

            email_to_profile[email] = profile
            username_to_profile[username] = profile
            if profile.employee_id:
                employee_id_to_profile[profile.employee_id] = profile

            if enable_login:
                from ..invites import create_user_invite

                create_user_invite(profile)

            parent_value = str(row.get("parent_participant", "")).strip()
            child_value = str(row.get("child_participant", "")).strip()
            if parent_value and child_value:
                parent_profile = (
                    username_to_profile.get(parent_value)
                    or employee_id_to_profile.get(parent_value)
                    or email_to_profile.get(parent_value)
                )
                child_profile = (
                    username_to_profile.get(child_value)
                    or employee_id_to_profile.get(child_value)
                    or email_to_profile.get(child_value)
                )
                if parent_profile and child_profile:
                    HierarchyRelationship.objects.update_or_create(
                        parent_participant=parent_profile,
                        child_participant=child_profile,
                        defaults={"split_percentage": split_percentage, "is_active": True},
                    )

            success += 1
        except Exception as exc:
            failed += 1
            errors.append({"row": index, "email": row.get("email", ""), "error": str(exc)})
            logger.exception("User import row %s failed", index)

    return {
        "success": success,
        "failed": failed,
        "errors": errors[:20],
        "total_rows": len(rows),
    }
