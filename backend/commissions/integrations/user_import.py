"""Import user rows from CRM sync (same column shape as User Setup CSV)."""

import logging
from datetime import datetime

from django.db.models import Q

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


def _org_profile_filter(organization):
    if organization:
        return Q(organization=organization) | Q(organization__isnull=True)
    return Q()


def _find_existing_profile(organization, email, crm_user_id="", crm_alt_user_id=""):
    """Find an existing profile by email or CRM ids within the org scope."""
    org_filter = _org_profile_filter(organization)
    if email:
        profile = UserProfile.objects.filter(org_filter, email__iexact=email).first()
        if profile:
            return profile
    if crm_user_id:
        profile = UserProfile.objects.filter(org_filter, crm_user_id=crm_user_id).first()
        if profile:
            return profile
    if crm_alt_user_id:
        profile = UserProfile.objects.filter(
            org_filter,
            crm_alt_user_id=crm_alt_user_id,
        ).first()
        if profile:
            return profile
    return None


def process_users_rows(
    organization,
    rows,
    *,
    allow_updates=True,
    login_via_invite=True,
    strict_csv=False,
):
    """
    Import UserProfile rows from dicts (CSV / CRM column names).
    Returns {success, failed, errors, total_rows}.

    strict_csv: require employee_id + role (CSV upload contract).
    login_via_invite: send activation invite emails for newly created login users.
    """
    success = 0
    failed = 0
    users_created = 0
    users_updated = 0
    activation_emails_sent = 0
    email_failures = 0
    errors = []
    records = []
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
            crm_alt_user_id_val = str(row.get("crm_alt_user_id", "")).strip()
            name_val = str(row.get("name", "")).strip()

            if strict_csv:
                if not str(row.get("role", "")).strip():
                    raise ValueError("role is required")
                if not employee_id_val:
                    raise ValueError("employee_id is required")

            if organization and (crm_user_id_val or crm_alt_user_id_val):
                existing_by_crm = _find_existing_profile(
                    organization,
                    email,
                    crm_user_id_val,
                    crm_alt_user_id_val,
                )
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

            existing_profile = _find_existing_profile(
                organization,
                email,
                crm_user_id_val,
                crm_alt_user_id_val,
            )

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
                "crm_alt_user_id": crm_alt_user_id_val,
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

            if allow_updates and existing_profile:
                for key, value in defaults.items():
                    setattr(existing_profile, key, value)
                if organization and not existing_profile.organization_id:
                    existing_profile.organization = organization
                existing_profile.save()
                profile = existing_profile
                created = False
            elif allow_updates:
                profile_lookup = {"email": email}
                if organization:
                    profile_lookup["organization"] = organization
                profile, created = UserProfile.objects.update_or_create(
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
                created = True

            email_to_profile[email] = profile
            username_to_profile[username] = profile
            if profile.employee_id:
                employee_id_to_profile[profile.employee_id] = profile

            invite_status = ""
            invite_error = ""
            if enable_login:
                if login_via_invite:
                    if created:
                        from ..invites import create_user_invite

                        _, _token, sent, invite_error = create_user_invite(profile)
                        if sent:
                            activation_emails_sent += 1
                            invite_status = "sent"
                        else:
                            email_failures += 1
                            invite_status = "email_failed"
                            logger.warning(
                                "Activation email failed for %s: %s",
                                email,
                                invite_error,
                            )
                    else:
                        from ..auth_utils import provision_login_user

                        provision_login_user(profile)
                        invite_status = "skipped_existing"
                else:
                    from ..auth_utils import provision_login_user

                    provision_login_user(profile)
                    invite_status = "provisioned"

            if created:
                users_created += 1
            else:
                users_updated += 1

            parent_value = str(row.get("parent_participant", "")).strip()
            child_value = str(row.get("child_participant", "")).strip()
            if parent_value and child_value:
                org_filter = _org_profile_filter(organization)

                def _resolve_hierarchy_ref(value):
                    profile_ref = (
                        username_to_profile.get(value)
                        or employee_id_to_profile.get(value)
                        or email_to_profile.get(value)
                    )
                    if profile_ref:
                        return profile_ref
                    qs = UserProfile.objects.filter(org_filter)
                    return (
                        qs.filter(username=value).first()
                        or qs.filter(employee_id=value).first()
                        or qs.filter(email__iexact=value).first()
                    )

                parent_profile = _resolve_hierarchy_ref(parent_value)
                child_profile = _resolve_hierarchy_ref(child_value)
                if parent_profile and child_profile:
                    HierarchyRelationship.objects.update_or_create(
                        parent_participant=parent_profile,
                        child_participant=child_profile,
                        defaults={"split_percentage": split_percentage, "is_active": True},
                    )

            success += 1
            record = {
                "row": index,
                "email": email,
                "name": name_val,
                "employee_id": profile.employee_id,
                "crm_user_id": crm_user_id_val,
                "status": "created" if created else "updated",
            }
            if invite_status:
                record["invite_status"] = invite_status
            if invite_error:
                record["invite_error"] = invite_error
            records.append(record)
        except Exception as exc:
            failed += 1
            errors.append({"row": index, "email": row.get("email", ""), "error": str(exc)})
            records.append({
                "row": index,
                "email": str(row.get("email", "")).strip(),
                "name": str(row.get("name", "")).strip(),
                "employee_id": str(row.get("employee_id", "")).strip(),
                "crm_user_id": str(row.get("crm_user_id", "")).strip(),
                "status": "failed",
                "error": str(exc),
            })
            logger.exception("User import row %s failed", index)

    return {
        "success": success,
        "failed": failed,
        "users_created": users_created,
        "users_updated": users_updated,
        "existing_users_skipped": users_updated,
        "activation_emails_sent": activation_emails_sent,
        "email_failures": email_failures,
        "errors": errors[:20],
        "records": records,
        "total_rows": len(rows),
    }
