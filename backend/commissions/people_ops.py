"""
People & Access Management — enrichment for UserProfile directory.

Does not change authentication or invite acceptance flow.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.utils import timezone


SYSTEM_ROLES = ("Admin", "Finance", "Manager", "Sales Rep")

ROLE_PERMISSIONS = {
    "Admin": [
        "view_plans",
        "manage_plans",
        "approve_transactions",
        "view_commissions",
        "export_reports",
        "manage_users",
        "view_orders",
        "create_orders",
    ],
    "Finance": [
        "view_plans",
        "approve_transactions",
        "view_commissions",
        "export_reports",
        "view_orders",
    ],
    "Manager": [
        "view_plans",
        "view_commissions",
        "export_reports",
        "view_orders",
        "approve_transactions",
    ],
    # Sales participants: own incentive / commission details only
    "Sales Rep": [
        "view_own_incentives",
    ],
}

PERMISSION_LABELS = {
    "view_plans": "View Plans",
    "manage_plans": "Manage Plans",
    "approve_transactions": "Approve Transactions",
    "view_commissions": "View Commissions",
    "view_own_incentives": "View own incentive details",
    "export_reports": "Export Reports",
    "manage_users": "Manage Users",
    "view_orders": "View Orders",
    "create_orders": "Create Orders",
}

SORTABLE_FIELDS = {
    "name": "name",
    "employee_id": "employee_id",
    "email": "email",
    "role": "role",
    "position": "position_name",
    "department": "department",
    "business_unit": "business_group",
    "region": "market",
    "quota": "personal_target",
    "created_at": "created_at",
}


def normalize_role(role):
    return str(role or "").strip()


def is_system_role(role):
    key = normalize_role(role)
    if key in ROLE_PERMISSIONS:
        return True
    return key.lower() in {r.lower() for r in ROLE_PERMISSIONS}


def permissions_for_role(role, custom_permissions=None):
    """Resolve effective permissions. Custom list overrides when provided."""
    if custom_permissions is not None and isinstance(custom_permissions, list):
        allowed = set(PERMISSION_LABELS.keys())
        return [c for c in custom_permissions if c in allowed]
    key = normalize_role(role)
    if key in ROLE_PERMISSIONS:
        return list(ROLE_PERMISSIONS[key])
    lowered = {k.lower(): v for k, v in ROLE_PERMISSIONS.items()}
    return list(lowered.get(key.lower(), ROLE_PERMISSIONS["Sales Rep"]))


def permission_rows(role, custom_permissions=None):
    granted = set(permissions_for_role(role, custom_permissions))
    return [
        {
            "code": code,
            "label": label,
            "granted": code in granted,
        }
        for code, label in PERMISSION_LABELS.items()
    ]


def _django_user_for_profile(profile):
    email = (profile.email or "").strip()
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()


def invitation_state(profile, invite=None):
    """Derive invite lifecycle for UI."""
    now = timezone.now()
    if invite is None:
        invite = (
            profile.login_invites.order_by("-created_at").first()
            if hasattr(profile, "login_invites")
            else None
        )
    if invite is None:
        return {
            "status": "none",
            "label": "Created",
            "lifecycle": "created",
            "expires_at": None,
            "sent_at": None,
            "opened_at": None,
            "accepted_at": None,
            "can_resend": bool(profile.enable_login),
            "can_revoke": False,
            "can_copy_link": bool(profile.enable_login),
        }
    opened_at = getattr(invite, "opened_at", None)
    if invite.accepted_at:
        return {
            "status": "accepted",
            "label": "Password Created",
            "lifecycle": "password_created",
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            "sent_at": invite.sent_at.isoformat() if invite.sent_at else None,
            "opened_at": opened_at.isoformat() if opened_at else None,
            "accepted_at": invite.accepted_at.isoformat(),
            "can_resend": False,
            "can_revoke": False,
            "can_copy_link": False,
        }
    if invite.expires_at and invite.expires_at <= now:
        return {
            "status": "expired",
            "label": "Invite Expired",
            "lifecycle": "expired",
            "expires_at": invite.expires_at.isoformat(),
            "sent_at": invite.sent_at.isoformat() if invite.sent_at else None,
            "opened_at": opened_at.isoformat() if opened_at else None,
            "accepted_at": None,
            "can_resend": True,
            "can_revoke": False,
            "can_copy_link": True,
        }
    if opened_at:
        return {
            "status": "opened",
            "label": "Invitation Opened",
            "lifecycle": "invitation_opened",
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            "sent_at": invite.sent_at.isoformat() if invite.sent_at else None,
            "opened_at": opened_at.isoformat(),
            "accepted_at": None,
            "can_resend": True,
            "can_revoke": True,
            "can_copy_link": True,
        }
    return {
        "status": "pending",
        "label": "Invitation Sent" if invite.sent_at else "Created",
        "lifecycle": "invitation_sent" if invite.sent_at else "created",
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "sent_at": invite.sent_at.isoformat() if invite.sent_at else None,
        "opened_at": None,
        "accepted_at": None,
        "can_resend": True,
        "can_revoke": True,
        "can_copy_link": True,
    }


def account_lifecycle(profile, invite=None, user=None, plan=None):
    """
    Participant lifecycle:
    Invited → Pending Activation → Active → Plan Assigned → Suspended → Inactive
    """
    stored = getattr(profile, "account_status", None) or ""
    if stored == "suspended":
        return "suspended", "Suspended"
    if stored == "deactivated":
        return "inactive", "Inactive"

    user = user or _django_user_for_profile(profile)
    invite_info = invitation_state(profile, invite)
    has_plan = bool(plan or getattr(profile, "assigned_compensation_plan_id", None))

    if invite_info["status"] in ("pending", "opened", "expired"):
        if invite_info["status"] == "pending" and not invite_info.get("sent_at"):
            return "invited", "Invited"
        return "pending_activation", "Pending Activation"

    activated = invite_info["status"] == "accepted" or (
        user is not None and user.has_usable_password()
    )

    if activated:
        if user and not user.is_active:
            return "suspended", "Suspended"
        if not profile.enable_login:
            return "inactive", "Inactive"
        if has_plan:
            return "plan_assigned", "Plan Assigned"
        return "active", "Active"

    if profile.enable_login:
        return "invited", "Invited"
    return "inactive", "Inactive"


def _calc_method_label(plan):
    if not plan:
        return ""
    table = str(getattr(plan, "commission_table_type", "") or "").upper()
    method = str(getattr(plan, "tier_calculation_method", "") or "").lower()
    if table == "FLAT":
        return "Flat Rate"
    if table == "MARGINAL" or method == "marginal":
        return "Progressive Rate"
    if table == "HIGHEST":
        return "Highest Rate"
    if method == "marginal":
        return "Progressive Rate"
    return "Rate Table"


def _format_money(amount, currency="INR"):
    try:
        value = Decimal(str(amount or 0))
    except Exception:
        value = Decimal("0")
    symbol = "₹" if str(currency or "").upper() in ("INR", "RS", "") else f"{currency} "
    return f"{symbol}{value:,.0f}"


def enrich_people_row(profile, *, manager=None, invite=None, user=None, plan=None, plan_name=None):
    user = user or _django_user_for_profile(profile)
    invite = invite or (
        profile.login_invites.order_by("-created_at").first()
        if hasattr(profile, "login_invites")
        else None
    )
    if plan is None:
        plan = getattr(profile, "assigned_compensation_plan", None)
    status_code, status_label = account_lifecycle(
        profile, invite=invite, user=user, plan=plan
    )
    invite_info = invitation_state(profile, invite)
    territory = getattr(profile, "territory", None)
    eligible = getattr(profile, "commission_eligible", True)
    if eligible is None:
        eligible = True
    custom_perms = getattr(profile, "custom_permissions", None) or None
    if custom_perms == []:
        custom_perms = []

    display = (
        profile.name
        or f"{profile.first_name} {profile.last_name}".strip()
        or profile.email
    )
    resolved_plan_name = (
        plan_name
        or (getattr(plan, "plan_name", None) if plan else "")
        or ""
    )
    currency = profile.personal_currency or "INR"
    effective = getattr(profile, "comp_effective_date", None)
    return {
        "id": profile.id,
        "display_name": display,
        "name": profile.name or display,
        "employee_id": profile.employee_id or "",
        "email": profile.email or "",
        "phone": getattr(profile, "phone", None) or "",
        "role": profile.role or "",
        "is_custom_role": not is_system_role(profile.role),
        "position": profile.position_name or profile.position_title or profile.title or "",
        "department": getattr(profile, "department", None) or profile.function_name or "",
        "business_unit": profile.business_group or "",
        "manager_name": (
            (manager.name or f"{manager.first_name} {manager.last_name}".strip() or manager.email)
            if manager
            else ""
        ),
        "manager_id": manager.id if manager else None,
        "region": profile.market or "",
        "territory_name": territory.name if territory else "",
        "territory_id": profile.territory_id,
        "status": status_code,
        "status_label": status_label,
        "participant_lifecycle": status_label,
        "commission_eligible": bool(eligible),
        "compensation_eligibility": "Eligible" if eligible else "Not Eligible",
        "assigned_plan_id": plan.id if plan else getattr(profile, "assigned_compensation_plan_id", None),
        "assigned_plan_name": resolved_plan_name,
        "compensation_plan": resolved_plan_name,
        "quota": str(profile.personal_target or 0),
        "quota_display": _format_money(profile.personal_target, currency),
        "personal_currency": currency,
        "calculation_method": _calc_method_label(plan),
        "comp_effective_date": effective.isoformat() if effective else None,
        "enable_login": profile.enable_login,
        "invitation": invite_info,
        "last_login": user.last_login.isoformat() if user and user.last_login else None,
        "hire_date": profile.hire_date.isoformat() if profile.hire_date else None,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "permissions": permission_rows(profile.role, custom_perms),
        "custom_permissions": list(custom_perms) if custom_perms is not None else None,
    }


def resolve_plan_for_profile(profile, organization=None):
    """Prefer explicit assignment, then position/role match."""
    from .models import CompensationPlan

    assigned = getattr(profile, "assigned_compensation_plan", None)
    if assigned is not None:
        return assigned
    assigned_id = getattr(profile, "assigned_compensation_plan_id", None)
    if assigned_id:
        plan = CompensationPlan.objects.filter(pk=assigned_id).first()
        if plan:
            return plan

    org = organization or profile.organization
    qs = CompensationPlan.objects.filter(status="Active")
    if org is not None:
        qs = qs.filter(organization=org)
    if profile.position_name:
        plan = qs.filter(position_name__iexact=profile.position_name).first()
        if plan:
            return plan
    if profile.role:
        plan = qs.filter(role__iexact=profile.role).first()
        if plan:
            return plan
    return None


def build_participant_compensation(profile, plan=None, organization=None):
    plan = plan or resolve_plan_for_profile(profile, organization)
    currency = profile.personal_currency or "INR"
    start = getattr(profile, "comp_effective_date", None) or (
        getattr(plan, "effective_start_date", None) if plan else None
    )
    end = getattr(plan, "effective_end_date", None) if plan else None
    period = ""
    if start or end:
        def _fmt(d):
            return d.strftime("%b %Y") if d else "…"
        period = f"{_fmt(start)}–{_fmt(end)}"
    eligible = getattr(profile, "commission_eligible", True)
    territory = getattr(profile, "territory", None)
    return {
        "commission_eligible": bool(eligible),
        "commission_eligible_label": "YES" if eligible else "NO",
        "assigned_plan": (
            {
                "id": plan.id,
                "plan_name": plan.plan_name,
                "status": plan.status,
                "commission_table_type": plan.commission_table_type,
                "tier_calculation_method": plan.tier_calculation_method,
            }
            if plan
            else None
        ),
        "assigned_plan_name": plan.plan_name if plan else "",
        "role": profile.role or "",
        "commission_role": profile.role or "",
        "quota": str(profile.personal_target or 0),
        "quota_display": _format_money(profile.personal_target, currency),
        "territory_name": territory.name if territory else "",
        "effective_period": period,
        "comp_effective_date": (
            profile.comp_effective_date.isoformat()
            if getattr(profile, "comp_effective_date", None)
            else None
        ),
        "calculation_method": _calc_method_label(plan),
    }


def build_quota_attainment(profile, organization=None):
    """Quota vs closed/success sales for the participant."""
    from .models import Order

    currency = profile.personal_currency or "INR"
    quota = Decimal(str(profile.personal_target or 0))
    emp_id = (profile.employee_id or "").strip()
    credited = Decimal("0")
    if emp_id:
        qs = Order.objects.filter(employee_id=emp_id, order_status="Success")
        if organization is not None:
            qs = qs.filter(organization=organization)
        total = qs.aggregate(total=Sum("sales_amount"))["total"] or 0
        credited = Decimal(str(total))
    pct = float((credited / quota) * 100) if quota > 0 else None
    remaining = quota - credited if quota > 0 else Decimal("0")
    return {
        "quota": str(quota),
        "quota_display": _format_money(quota, currency),
        "credited_sales": str(credited),
        "credited_sales_display": _format_money(credited, currency),
        "remaining": str(remaining if remaining > 0 else 0),
        "remaining_display": _format_money(remaining if remaining > 0 else 0, currency),
        "attainment_pct": round(pct, 1) if pct is not None else None,
        "effective_date": (
            profile.comp_effective_date.isoformat()
            if getattr(profile, "comp_effective_date", None)
            else None
        ),
        "currency": currency,
    }


def build_hierarchy_chain(profile, organization=None, max_depth=8):
    """Walk managers upward → root-first list for visualization."""
    from .models import HierarchyRelationship

    chain = []
    seen = set()
    current = profile
    while current and current.id not in seen and len(chain) < max_depth:
        seen.add(current.id)
        chain.append(
            {
                "id": current.id,
                "name": current.name
                or f"{current.first_name} {current.last_name}".strip()
                or current.email,
                "role": current.role or "",
                "employee_id": current.employee_id or "",
                "is_self": current.id == profile.id,
            }
        )
        qs = HierarchyRelationship.objects.filter(
            child_participant=current, is_active=True
        ).select_related("parent_participant")
        if organization is not None:
            qs = qs.filter(parent_participant__organization=organization)
        rel = qs.first()
        current = rel.parent_participant if rel else None
    chain.reverse()
    return chain


def build_sales_performance(profile, organization=None):
    from .models import Order

    emp_id = (profile.employee_id or "").strip()
    if not emp_id:
        return {
            "order_count": 0,
            "total_sales": "0",
            "total_sales_display": _format_money(0, profile.personal_currency),
            "success_count": 0,
            "recent_orders": [],
        }
    qs = Order.objects.filter(employee_id=emp_id)
    if organization is not None:
        qs = qs.filter(organization=organization)
    agg = qs.aggregate(total=Sum("sales_amount"), count=Count("id"))
    success = qs.filter(order_status="Success").count()
    recent = []
    for order in qs.order_by("-order_date", "-id")[:12]:
        recent.append(
            {
                "id": order.id,
                "order_id": order.order_id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "sales_amount": str(order.sales_amount or 0),
                "order_status": order.order_status,
                "product_name": getattr(order, "product_name", "") or "",
            }
        )
    total = agg["total"] or 0
    return {
        "order_count": agg["count"] or 0,
        "total_sales": str(total),
        "total_sales_display": _format_money(total, profile.personal_currency),
        "success_count": success,
        "recent_orders": recent,
    }


def build_commission_history(profile, organization=None):
    from .models import Commission, Employee

    email = (profile.email or "").strip()
    if not email:
        return []
    from .tenants import tenant_org_q

    emp_qs = Employee.objects.filter(email__iexact=email)
    if organization is not None:
        emp_qs = emp_qs.filter(tenant_org_q(organization))
    employee = emp_qs.first()
    if not employee:
        return []
    qs = Commission.objects.filter(employee=employee).select_related(
        "compensation_plan", "sale"
    )
    if organization is not None:
        qs = qs.filter(tenant_org_q(organization))
    rows = []
    for c in qs.order_by("-calculated_at", "-id")[:40]:
        rows.append(
            {
                "id": c.id,
                "amount": str(c.commission_amount),
                "amount_display": _format_money(c.commission_amount, profile.personal_currency),
                "status": c.status,
                "plan_name": c.compensation_plan.plan_name if c.compensation_plan_id else "",
                "calculated_at": c.calculated_at.isoformat() if c.calculated_at else None,
            }
        )
    return rows


def build_people_summary(organization, queryset):
    qs = queryset
    total = qs.count()
    admins = qs.filter(role__iexact="Admin").count()
    sales = qs.filter(
        Q(role__icontains="Sales") | Q(role__iexact="Sales Rep")
    ).count()
    managers = qs.filter(role__icontains="Manager").count()

    from .models import UserInvite

    now = timezone.now()
    pending_invites = UserInvite.objects.filter(
        accepted_at__isnull=True,
        expires_at__gt=now,
    )
    if organization is not None:
        pending_invites = pending_invites.filter(organization=organization)
    pending_count = pending_invites.count()

    active = 0
    inactive = 0
    for profile in qs.select_related("territory")[:2000]:
        code, _ = account_lifecycle(profile)
        if code in ("active", "plan_assigned"):
            active += 1
        elif code in ("inactive", "suspended"):
            inactive += 1

    return {
        "total_employees": total,
        "active_users": active,
        "pending_invitations": pending_count,
        "inactive_users": inactive,
        "admins": admins,
        "managers": managers,
        "sales_participants": sales,
    }


def revoke_pending_invite(profile):
    now = timezone.now()
    return profile.login_invites.filter(
        accepted_at__isnull=True,
        expires_at__gt=now,
    ).update(expires_at=now)


def mark_invite_opened(invite):
    if invite and not invite.accepted_at and not getattr(invite, "opened_at", None):
        invite.opened_at = timezone.now()
        invite.save(update_fields=["opened_at", "updated_at"])
        return True
    return False


KNOWN_ROLES = {r.lower() for r in SYSTEM_ROLES}


def validate_users_csv_rows(rows, organization):
    """Dry-run validation + preview for employee CSV import."""
    from .models import CompensationPlan, UserProfile

    existing_emails = {
        e.lower()
        for e in UserProfile.objects.filter(organization=organization)
        .exclude(email="")
        .values_list("email", flat=True)
    }
    existing_ids = {
        str(eid).strip().upper()
        for eid in UserProfile.objects.filter(organization=organization)
        .exclude(employee_id="")
        .values_list("employee_id", flat=True)
    }
    active_plans = {
        p.lower()
        for p in CompensationPlan.objects.filter(
            organization=organization, status="Active"
        ).values_list("plan_name", flat=True)
    }
    active_positions = {
        (p or "").lower()
        for p in CompensationPlan.objects.filter(
            organization=organization, status="Active"
        ).values_list("position_name", flat=True)
        if p
    }

    seen_emails = set()
    seen_ids = set()
    preview = []
    errors = []
    warnings = []
    valid = 0

    for idx, raw in enumerate(rows, start=2):
        row = {str(k).strip().lower(): (v if v is not None else "") for k, v in raw.items()}
        email = str(row.get("email") or "").strip().lower()
        emp_id = str(row.get("employee_id") or "").strip()
        role = str(row.get("role") or "").strip()
        name = str(row.get("name") or "").strip()
        manager = str(row.get("manager") or row.get("manager_email") or row.get("manager_id") or "").strip()
        plan_hint = str(
            row.get("compensation_plan") or row.get("plan") or row.get("position_name") or ""
        ).strip()
        row_errors = []

        if not email:
            row_errors.append("Missing email")
        elif email in existing_emails:
            row_errors.append("Duplicate email (already exists)")
        elif email in seen_emails:
            row_errors.append("Duplicate email (in file)")

        if emp_id:
            key = emp_id.upper()
            if key in existing_ids:
                row_errors.append("Duplicate employee ID (already exists)")
            elif key in seen_ids:
                row_errors.append("Duplicate employee ID (in file)")

        if role and role.lower() not in KNOWN_ROLES:
            warnings.append({"row": idx, "warning": f"Custom role '{role}' — verify permissions after import"})

        if not role:
            row_errors.append("Invalid / missing role")

        if manager:
            mgr_ok = UserProfile.objects.filter(
                organization=organization
            ).filter(
                Q(email__iexact=manager)
                | Q(employee_id__iexact=manager)
                | Q(name__iexact=manager)
            ).exists()
            if not mgr_ok:
                row_errors.append("Missing manager (not found in directory)")

        if plan_hint:
            low = plan_hint.lower()
            if low not in active_plans and low not in active_positions:
                warnings.append(
                    {"row": idx, "warning": f"Compensation plan/position '{plan_hint}' not matched"}
                )

        if email:
            seen_emails.add(email)
        if emp_id:
            seen_ids.add(emp_id.upper())

        status = "error" if row_errors else "ok"
        if row_errors:
            for msg in row_errors:
                errors.append({"row": idx, "error": msg, "email": email, "employee_id": emp_id})
        else:
            valid += 1

        preview.append(
            {
                "row": idx,
                "name": name,
                "email": email,
                "employee_id": emp_id,
                "role": role,
                "manager": manager,
                "plan": plan_hint,
                "status": status,
                "errors": row_errors,
            }
        )

    return {
        "total_rows": len(rows),
        "valid_rows": valid,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:50],
        "warnings": warnings[:50],
        "preview": preview[:100],
        "can_import": valid > 0 and len(errors) == 0,
    }
