"""
Catalog helpers for compensation plans (summary, filters, participants).
Assignment mirrors commission calculation: position_name first, then role
(when the plan has no position_name).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Q, Prefetch
from django.utils import timezone

from .models import (
    AuditLog,
    CommissionPlanVersion,
    CompensationPlan,
    UserProfile,
)
from .plan_versions import display_version_for_plan


def _org_plans(organization):
    qs = CompensationPlan.objects.all()
    if organization is not None:
        qs = qs.filter(organization=organization)
    return qs


def apply_plan_list_filters(qs, params):
    """Filter plan queryset from request query params (backward compatible)."""
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(plan_name__icontains=q)
            | Q(role__icontains=q)
            | Q(position_name__icontains=q)
            | Q(business_group__icontains=q)
            | Q(description__icontains=q)
            | Q(title__icontains=q)
            | Q(owner__icontains=q)
            | Q(approver__icontains=q)
            | Q(plan_type__icontains=q)
            | Q(versions__status__icontains=q)
            | Q(commission_table_type__icontains=q)
        ).distinct()

    role = (params.get("role") or "").strip()
    if role:
        qs = qs.filter(role__iexact=role)

    table_type = (params.get("commission_table_type") or "").strip()
    if table_type:
        qs = qs.filter(commission_table_type__iexact=table_type)

    business_group = (params.get("business_group") or "").strip()
    if business_group:
        qs = qs.filter(business_group__iexact=business_group)

    plan_type = (params.get("plan_type") or "").strip()
    if plan_type:
        qs = qs.filter(plan_type__iexact=plan_type)

    owner = (params.get("owner") or "").strip()
    if owner:
        qs = qs.filter(owner__icontains=owner)

    approver = (params.get("approver") or "").strip()
    if approver:
        qs = qs.filter(approver__icontains=approver)

    status = (params.get("status") or "").strip()
    version_status = (params.get("version_status") or "").strip()
    if status and status.lower() in ("draft", "active", "inactive"):
        qs = qs.filter(status__iexact=status)
    if version_status:
        qs = qs.filter(versions__status__iexact=version_status).distinct()
    elif status and status.lower() in ("published", "archived"):
        qs = qs.filter(versions__status__iexact=status).distinct()

    effective_on = (params.get("effective_on") or "").strip()
    if effective_on:
        try:
            on = date.fromisoformat(effective_on)
            qs = qs.filter(
                Q(effective_start_date__isnull=True) | Q(effective_start_date__lte=on),
                Q(effective_end_date__isnull=True) | Q(effective_end_date__gte=on),
            )
        except ValueError:
            pass

    return qs


def participants_queryset_for_plan(plan, organization=None):
    """
    UserProfiles that would be covered by this plan under calc matching rules.
    """
    org = organization if organization is not None else plan.organization
    qs = UserProfile.objects.select_related("territory")
    if org is not None:
        qs = qs.filter(organization=org)

    pos = (plan.position_name or "").strip()
    role = (plan.role or "").strip()

    if pos:
        return qs.filter(position_name__iexact=pos).order_by("name", "email")

    if role:
        return qs.filter(role__iexact=role).order_by("name", "email")

    return qs.none()


def participant_count_for_plan(plan, organization=None):
    return participants_queryset_for_plan(plan, organization).count()


def _accelerator_count(version):
    if version is None:
        return 0
    return (
        version.commission_rules.filter(
            Q(rule_type="multiplier") | Q(multiplier__gt=1)
        )
        .distinct()
        .count()
    )


def _bonus_rule_count(version):
    if version is None:
        return 0
    return (
        version.commission_rules.filter(
            Q(results__result_classification__icontains="bonus")
            | Q(results__result_classification__icontains="spiff")
            | Q(results__result_rate_type__icontains="bonus")
        )
        .distinct()
        .count()
    )


def _component(key, label, configured, count=None, detail=""):
    return {
        "key": key,
        "label": label,
        "configured": bool(configured),
        "status": "Configured" if configured else "Not Configured",
        "count": count,
        "detail": detail or "",
    }


def build_plan_components(plan, version, counts, participant_count):
    """Enterprise component checklist for cards and overview."""
    rates_ok = (counts.get("rates_count") or 0) > 0
    rules_ok = (counts.get("rules_count") or 0) > 0
    quotas_ok = (counts.get("quotas_count") or 0) > 0
    tier_bonuses = counts.get("bonus_tiers_count") or 0
    rule_bonuses = _bonus_rule_count(version)
    bonuses_ok = tier_bonuses > 0 or rule_bonuses > 0
    accelerators = _accelerator_count(version)
    eligibility_ok = bool(
        (plan.position_name or "").strip() or (plan.role or "").strip()
    )
    participants_ok = (participant_count or 0) > 0

    return [
        _component("rate_tables", "Rate Tables", rates_ok, counts.get("rates_count")),
        _component("rules", "Rules", rules_ok, counts.get("rules_count")),
        _component("monthly_quotas", "Monthly Quotas", quotas_ok, counts.get("quotas_count")),
        _component(
            "bonuses",
            "Bonuses",
            bonuses_ok,
            tier_bonuses + rule_bonuses,
            "Tier bonuses and bonus/spiff rule results",
        ),
        _component(
            "accelerators",
            "Accelerators",
            accelerators > 0,
            accelerators,
            "Multiplier rules",
        ),
        _component(
            "eligibility",
            "Eligibility",
            eligibility_ok,
            None,
            "Matched by position" if (plan.position_name or "").strip() else "Matched by role",
        ),
        _component(
            "participants",
            "Participants",
            participants_ok,
            participant_count,
        ),
    ]


def build_plan_warnings(plan, version, counts, participant_count, today=None):
    """Actionable configuration warnings for admins."""
    today = today or timezone.localdate()
    warnings = []
    rates = counts.get("rates_count") or 0
    rules = counts.get("rules_count") or 0
    quotas = counts.get("quotas_count") or 0
    participants = participant_count or 0

    if rates == 0:
        warnings.append(
            {"code": "no_rate_table", "severity": "warning", "message": "No Rate Table"}
        )
    if rules == 0:
        warnings.append(
            {"code": "no_rules", "severity": "info", "message": "No Rules Configured"}
        )
    if quotas == 0:
        warnings.append(
            {"code": "missing_quotas", "severity": "warning", "message": "Missing Quotas"}
        )
    if participants == 0:
        warnings.append(
            {
                "code": "no_participants",
                "severity": "critical",
                "message": "No Participants",
            }
        )

    if version is None:
        warnings.append(
            {
                "code": "no_version",
                "severity": "critical",
                "message": "No Version",
            }
        )
    else:
        if version.status == "Published" and version.effective_to and version.effective_to < today:
            warnings.append(
                {
                    "code": "expired_version",
                    "severity": "critical",
                    "message": "Expired Version",
                }
            )
        elif version.effective_to and 0 <= (version.effective_to - today).days <= 30:
            warnings.append(
                {
                    "code": "expires_soon",
                    "severity": "warning",
                    "message": "Plan Expires Soon",
                }
            )
        if version.status == "Draft" and version.created_at:
            age = timezone.now() - version.created_at
            if age.days > 30:
                warnings.append(
                    {
                        "code": "stale_draft",
                        "severity": "warning",
                        "message": "Draft Older Than 30 Days",
                    }
                )

    if not (plan.position_name or "").strip() and not (plan.role or "").strip():
        warnings.append(
            {
                "code": "no_eligibility",
                "severity": "critical",
                "message": "No Participants Assigned",
            }
        )

    return warnings


def compute_health_score(components, warnings, version=None):
    """
    Explainable Compensation Readiness score (0–100).

    Weighted checklist (20 pts each):
    Rate Tables, Eligibility, Participants, Rules, Quotas.
    """
    by_key = {c["key"]: c for c in components}
    today = timezone.localdate()

    weights = [
        ("rate_tables", "Rate Tables", 20, True),
        ("eligibility", "Eligibility", 20, True),
        ("participants", "Participants", 20, True),
        ("rules", "Rules", 20, False),
        ("monthly_quotas", "Quotas", 20, False),
    ]

    breakdown = []
    score = 0
    for key, label, points, required in weights:
        configured = bool(by_key.get(key, {}).get("configured"))
        earned = points if configured else 0
        # Partial credit for quotas if some months exist but incomplete year
        if key == "monthly_quotas" and not configured:
            count = by_key.get(key, {}).get("count") or 0
            if count:
                earned = min(points, int(round(points * min(count, 12) / 12)))
        score += earned
        breakdown.append(
            {
                "key": key,
                "label": label,
                "earned": earned,
                "max": points,
                "ok": earned >= points,
                "required": required,
                "display": f"{earned}/{points}",
            }
        )

    # Soft penalties for expired / unpublished (do not exceed remaining headroom)
    active_version = bool(version and version.status == "Published")
    dates_valid = True
    if version and version.effective_to and version.effective_to < today:
        dates_valid = False
    if not active_version:
        score = max(0, score - 8)
    if not dates_valid:
        score = max(0, score - 8)

    score = max(0, min(100, score))
    if score >= 85:
        status = "Healthy"
        level = "healthy"
        readiness = "Ready for commission processing"
    elif score >= 60:
        status = "Review Required"
        level = "warning"
        readiness = "Review required before commission processing"
    else:
        status = "Critical Attention"
        level = "critical"
        readiness = "Not ready for commission processing"

    contributors = [
        {
            "key": row["key"],
            "label": row["label"],
            "ok": row["ok"],
            "required": row["required"],
            "earned": row["earned"],
            "max": row["max"],
            "display": row["display"],
        }
        for row in breakdown
    ]
    contributors.append(
        {
            "key": "active_version",
            "label": "Published Version",
            "ok": active_version,
            "required": True,
        }
    )
    contributors.append(
        {
            "key": "effective_dates",
            "label": "Effective Dates Valid",
            "ok": dates_valid,
            "required": True,
        }
    )

    missing = []
    for row in breakdown:
        if not row["ok"]:
            if row["key"] == "rules":
                missing.append("Add commission rules")
            elif row["key"] == "monthly_quotas":
                missing.append("Configure monthly quotas")
            elif row["key"] == "rate_tables":
                missing.append("Configure rate tables")
            elif row["key"] == "participants":
                missing.append("Assign participants")
            elif row["key"] == "eligibility":
                missing.append("Define eligibility (role or position)")

    recommendations = list(missing)
    for w in warnings[:4]:
        if w["message"] not in recommendations:
            recommendations.append(w["message"])

    return {
        "score": score,
        "status": status,
        "level": level,
        "readiness": readiness,
        "label": "Compensation Readiness",
        "breakdown": breakdown,
        "contributors": contributors,
        "missing": missing,
        "recommendations": recommendations[:8],
    }


def build_configuration_health(plan, version, counts, participant_count, components):
    """Per-component status for Configuration Health section."""
    owner = last_published_by_email(plan, version) or created_by_email(plan) or "—"
    version_label = f"v{version.version_number}" if version else "—"
    updated = None
    if version and getattr(version, "updated_at", None):
        updated = version.updated_at.isoformat()
    elif getattr(plan, "updated_at", None):
        updated = plan.updated_at.isoformat()

    total = len(components) or 1
    configured_n = sum(1 for c in components if c.get("configured"))
    overall_completion = round(100 * configured_n / total)

    rows = []
    for comp in components:
        rows.append(
            {
                **comp,
                "completion_pct": 100 if comp.get("configured") else 0,
                "last_updated": updated,
                "owner": owner,
                "version": version_label,
                "items": comp.get("count"),
            }
        )

    # Approval workflow row
    approval_ok = bool(version and version.status == "Published")
    rows.append(
        {
            "key": "approval_workflow",
            "label": "Approval Workflow",
            "configured": approval_ok,
            "status": "Configured" if approval_ok else "Not Configured",
            "count": 1 if approval_ok else 0,
            "detail": version.status if version else "No version",
            "completion_pct": 100 if approval_ok else 0,
            "last_updated": updated,
            "owner": owner,
            "version": version_label,
            "items": 1 if approval_ok else 0,
        }
    )

    return {
        "overall_completion_pct": overall_completion,
        "rows": rows,
    }


def build_action_center(plan, version, warnings, components):
    """Actionable next steps for administrators."""
    actions = []
    by_key = {c["key"]: c for c in components}
    plan_id = plan.id

    def add(code, title, detail, href, cta, severity="warning"):
        actions.append(
            {
                "code": code,
                "title": title,
                "detail": detail,
                "href": href,
                "cta": cta,
                "severity": severity,
            }
        )

    if not by_key.get("monthly_quotas", {}).get("configured"):
        add(
            "missing_quotas",
            "Missing Monthly Quotas",
            "Quota attainment and forecasts need monthly targets.",
            f"/comp-plans/{plan_id}/quotas",
            "Configure Quotas",
        )
    if not by_key.get("rules", {}).get("configured"):
        add(
            "no_rules",
            "No Rules Configured",
            "Add eligibility or payout rules for edge cases and multipliers.",
            f"/comp-plans/{plan_id}/rules",
            "Create Rule",
            "info",
        )
    if not by_key.get("rate_tables", {}).get("configured"):
        add(
            "no_rates",
            "No Rate Table",
            "Commission calculation requires at least one rate band.",
            f"/comp-plans/{plan_id}/rates",
            "Configure Rates",
            "critical",
        )
    if not by_key.get("participants", {}).get("configured"):
        add(
            "no_participants",
            "No Participants Assigned",
            "No employees match this plan's position or role.",
            f"/comp-plans/{plan_id}/participants",
            "Assign Participants",
            "critical",
        )
    if version and version.status == "Draft":
        add(
            "draft_ready",
            "Draft Ready",
            "Review rates and rules, then publish to put this version live.",
            f"/comp-plans/{plan_id}/versions",
            "Publish Version",
            "info",
        )
    if version and version.status == "Published" and version.effective_to:
        today = timezone.localdate()
        if 0 <= (version.effective_to - today).days <= 30:
            add(
                "expires_soon",
                "Plan Expires Soon",
                f"Effective end date is {version.effective_to}. Clone and extend if needed.",
                f"/comp-plans/{plan_id}/versions",
                "Manage Versions",
            )

    # Deduplicate by code from warnings already covered
    return actions[:8]


def build_coverage_summary(plan, organization=None, limit=12):
    """Distinct coverage dimensions among matched participants."""
    qs = participants_queryset_for_plan(plan, organization)
    employees = qs.count()

    def _distinct(field, exclude_blank=True):
        q = qs
        if exclude_blank:
            q = q.exclude(**{field: ""})
        return [v for v in q.values_list(field, flat=True).distinct()[:limit] if v]

    departments = _distinct("function_name")
    managers = _distinct("hierarchy")
    positions = _distinct("position_name")
    markets = _distinct("market")
    territories = list(
        qs.filter(territory__isnull=False)
        .values_list("territory__name", flat=True)
        .distinct()[:limit]
    )
    regions = []
    for item in markets + territories:
        if item and item not in regions:
            regions.append(item)
        if len(regions) >= limit:
            break
    # Countries: reuse market when it looks like a geography label; no dedicated field.
    countries = markets[:limit]
    sales_teams = _distinct("title_category") or _distinct("title")
    business_units = _distinct("business_group")
    plan_bu = (plan.business_group or "").strip()
    if plan_bu and plan_bu not in business_units:
        business_units = [plan_bu] + business_units

    by_region_qs = (
        qs.exclude(market="")
        .values("market")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    by_region = [
        {"label": row["market"], "count": row["count"]}
        for row in by_region_qs
        if row["market"]
    ]
    if not by_region:
        by_region = [
            {"label": row["territory__name"], "count": row["count"]}
            for row in qs.filter(territory__isnull=False)
            .values("territory__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
            if row["territory__name"]
        ]

    by_department = [
        {"label": row["function_name"], "count": row["count"]}
        for row in qs.exclude(function_name="")
        .values("function_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
        if row["function_name"]
    ]

    return {
        "employees_assigned": employees,
        "departments": departments,
        "managers": managers,
        "regions": regions,
        "countries": countries,
        "territories": [t for t in territories if t],
        "positions": positions,
        "sales_teams": sales_teams,
        "business_units": business_units,
        "department_count": len(departments),
        "region_count": len(regions),
        "business_unit_count": len(business_units),
        "charts": {
            "employees_by_region": by_region,
            "employees_by_department": by_department,
        },
    }


def build_business_summary(plan, version=None):
    """Short business narrative fields for cards and overview."""
    role = (plan.role or "").strip() or "Unassigned role"
    position = (plan.position_name or "").strip()
    who = (
        f"Employees in position “{position}”"
        if position
        else f"Employees with role “{role}”"
    )
    table = (version.commission_table_type if version else plan.commission_table_type) or ""
    method_labels = {
        "RATE": "Rate tiers",
        "HIGHEST": "Highest rate",
        "MARGINAL": "Marginal rate",
        "FLAT": "Flat rate",
        "LOOKUP": "Lookup table",
    }
    return {
        "purpose": (plan.description or "").strip()
        or f"Compensation plan for {role}.",
        "who_receives": who,
        "calculation_method": method_labels.get(table.upper(), table or "—"),
        "business_unit": (plan.business_group or "").strip() or "—",
        "sales_organization": (plan.title or "").strip()
        or (plan.business_group or "").strip()
        or "—",
        "typical_users": position or role,
        "plan_basis": plan.plan_basis or "—",
    }


def last_published_by_email(plan, version=None):
    published = None
    if version and version.status == "Published" and version.published_by_id:
        published = version
    if published is None:
        published = (
            plan.versions.filter(status="Published", published_by__isnull=False)
            .order_by("-published_at", "-version_number")
            .select_related("published_by")
            .first()
        )
    if published and published.published_by:
        return published.published_by.email or published.published_by.username
    return None


def created_by_email(plan):
    """Best-effort creator from audit trail (no schema change)."""
    row = (
        AuditLog.objects.filter(
            action="compensation_plan_created",
            detail__plan_id=plan.id,
        )
        .order_by("created_at")
        .first()
    )
    if row and row.user_email:
        return row.user_email
    return None


def enrich_plan_card_fields(plan, version=None):
    """Lightweight counts for catalog cards (mutates nothing; returns dict)."""
    version = version if version is not None else display_version_for_plan(plan)
    if version is None:
        rates = (
            plan.sc_rate_tables.count()
            + plan.sc_flat_rate_tables.count()
            + plan.sc_lookup_tables.count()
        )
        rules = plan.commission_rules.count()
        quotas = 0
        bonus_tiers = 0
        last_published_at = None
    else:
        rates = (
            version.sc_rate_tables.count()
            + version.sc_flat_rate_tables.count()
            + version.sc_lookup_tables.count()
        )
        rules = version.commission_rules.count()
        quotas = version.quotas.count()
        bonus_tiers = (
            version.sc_rate_tables.filter(bonus_amount__gt=0).count()
            + version.sc_flat_rate_tables.filter(bonus_amount__gt=0).count()
            + version.sc_lookup_tables.filter(bonus_amount__gt=0).count()
        )
        last_published_at = (
            version.published_at.isoformat() if version.published_at else None
        )
        if not last_published_at:
            published = (
                plan.versions.filter(status="Published")
                .order_by("-published_at", "-version_number")
                .first()
            )
            if published and published.published_at:
                last_published_at = published.published_at.isoformat()

    return {
        "rates_count": rates,
        "rules_count": rules,
        "quotas_count": quotas,
        "bonus_tiers_count": bonus_tiers,
        "last_published_at": last_published_at,
    }


def enrich_plan_enterprise_fields(
    plan,
    version=None,
    organization=None,
    participant_count=None,
    include_coverage=True,
):
    """
    Enterprise card/overview payload layered on count enrichment.
    Backward compatible: callers still get rates_count etc.
    """
    version = version if version is not None else display_version_for_plan(plan)
    counts = enrich_plan_card_fields(plan, version)
    if participant_count is None:
        participant_count = participant_count_for_plan(plan, organization)

    components = build_plan_components(plan, version, counts, participant_count)
    warnings = build_plan_warnings(plan, version, counts, participant_count)
    health = compute_health_score(components, warnings, version)
    configuration_health = build_configuration_health(
        plan, version, counts, participant_count, components
    )
    actions = build_action_center(plan, version, warnings, components)
    versions_preview = build_versions_preview(plan)
    ops = build_ops_metrics(plan, organization)
    calc_status = build_calculation_status(components, version, health)

    coverage = (
        build_coverage_summary(plan, organization)
        if include_coverage
        else {
            "employees_assigned": participant_count or 0,
            "departments": [],
            "managers": [],
            "regions": [],
            "countries": [],
            "territories": [],
            "positions": [],
            "sales_teams": [],
            "business_units": [plan.business_group]
            if (plan.business_group or "").strip()
            else [],
            "department_count": 0,
            "region_count": 0,
            "business_unit_count": 1 if (plan.business_group or "").strip() else 0,
            "charts": {"employees_by_region": [], "employees_by_department": []},
        }
    )

    last_mod = None
    if getattr(plan, "last_modified_by_id", None) and plan.last_modified_by:
        last_mod = plan.last_modified_by.email or plan.last_modified_by.username

    payload = {
        **counts,
        "participant_count": participant_count,
        "components": components,
        "warnings": warnings,
        "health": health,
        "configuration_health": configuration_health,
        "actions": actions,
        "coverage": coverage,
        "business_summary": build_business_summary(plan, version),
        "last_published_by": last_published_by_email(plan, version),
        "created_by": created_by_email(plan),
        "accelerators_count": _accelerator_count(version),
        "bonus_rules_count": _bonus_rule_count(version),
        "versions_preview": versions_preview,
        "ops_metrics": ops,
        "plan_type": getattr(plan, "plan_type", "") or "sales_commission",
        "plan_type_label": dict(CompensationPlan.PLAN_TYPE_CHOICES).get(
            getattr(plan, "plan_type", None), "Sales Commission"
        ),
        "owner": getattr(plan, "owner", "") or "",
        "approver": getattr(plan, "approver", "") or "",
        "last_modified_by_email": last_mod,
        "last_modified_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "calculation_status": calc_status,
        "approval_status": calc_status.get("approval_status"),
    }
    return payload


def build_ops_metrics(plan, organization=None):
    """Operational commission metrics for catalog cards and overview."""
    from django.db.models import Avg, Count, Max, Sum

    from .models import Commission

    qs = Commission.objects.filter(compensation_plan=plan)
    if organization is not None:
        qs = qs.filter(organization=organization)

    agg = qs.aggregate(
        total=Sum("commission_amount"),
        avg=Avg("commission_amount"),
        tx=Count("id"),
        last_calc=Max("calculated_at"),
        employees=Count("employee_id", distinct=True),
    )
    successful = qs.exclude(status__isnull=True).order_by("-calculated_at").first()
    return {
        "last_calculation": agg["last_calc"].isoformat() if agg["last_calc"] else None,
        "last_successful_calculation": (
            successful.calculated_at.isoformat()
            if successful and successful.calculated_at
            else None
        ),
        "transactions_processed": agg["tx"] or 0,
        "employees_paid": agg["employees"] or 0,
        "total_commission_generated": float(agg["total"]) if agg["total"] is not None else 0,
        "average_commission": float(agg["avg"]) if agg["avg"] is not None else None,
        "estimated_monthly_commission": float(agg["avg"]) if agg["avg"] is not None else None,
    }


def build_calculation_status(components, version, health=None):
    """
    Whether the plan can run commission calculation reliably.
    Blockers: no rates, no eligibility, no participants, expired published version.
    Rules/quotas are warnings but rates+eligibility+participants are hard blockers.
    """
    by_key = {c["key"]: c for c in components}
    reasons = []
    if not by_key.get("rate_tables", {}).get("configured"):
        reasons.append("Missing Rate Tables")
    if not by_key.get("eligibility", {}).get("configured"):
        reasons.append("Missing Eligibility")
    if not by_key.get("participants", {}).get("configured"):
        reasons.append("No Participants")
    if not by_key.get("rules", {}).get("configured"):
        reasons.append("Missing Rules")
    if not by_key.get("monthly_quotas", {}).get("configured"):
        reasons.append("Missing Quotas")

    today = timezone.localdate()
    if version and version.status == "Published" and version.effective_to and version.effective_to < today:
        reasons.append("Expired Version")
    if version is None:
        reasons.append("No Version")
    elif version.status == "Draft":
        reasons.append("Draft Not Published")

    hard = {
        "Missing Rate Tables",
        "Missing Eligibility",
        "No Participants",
        "Expired Version",
        "No Version",
    }
    blocked = any(r in hard for r in reasons)
    # Draft without rates is blocked; draft with config is "pending publish" but can still simulate
    if blocked:
        status = "blocked"
        label = "Calculation Blocked"
    elif version and version.status == "Draft":
        status = "pending"
        label = "Ready — Publish to Activate"
    else:
        status = "ready"
        label = "Ready for Calculation"

    return {
        "status": status,
        "label": label,
        "ready": status == "ready",
        "blocked": status == "blocked",
        "reasons": reasons,
        "approval_status": (
            "Published"
            if version and version.status == "Published"
            else "Pending Approval"
            if version and version.status == "Draft"
            else version.status
            if version
            else "None"
        ),
    }


def build_action_center_items(attention_buckets):
    """
    Aggregate catalog Action Center rows from plan issue buckets.
    """
    catalog = [
        (
            "missing_rules",
            "Commission Rules Required",
            "Plans blocked from accurate commission calculation",
            "Fix Now",
            "rules",
        ),
        (
            "missing_quotas",
            "Missing Quotas",
            "Quota attainment calculations unavailable",
            "Fix Now",
            "quotas",
        ),
        (
            "no_participants",
            "No Participants",
            "Employees cannot receive commissions",
            "Fix Now",
            "participants",
        ),
        (
            "expires_soon",
            "Expiring Versions",
            "Future payouts may fail",
            "Fix Now",
            "versions",
        ),
        (
            "no_rates",
            "Rate Tables Required",
            "Commission calculation cannot run",
            "Fix Now",
            "rates",
        ),
    ]
    items = []
    for code, title, impact, cta, tab in catalog:
        plans = attention_buckets.get(code) or []
        if not plans:
            continue
        count = len(plans)
        first = plans[0]
        items.append(
            {
                "code": code,
                "title": title,
                "subtitle": f"{count} plan{'s' if count != 1 else ''} — {impact}",
                "impact": impact,
                "count": count,
                "cta": cta,
                "href": f"/comp-plans/{first['id']}/{tab}",
                "plan_ids": [p["id"] for p in plans[:10]],
            }
        )
    return items


def build_versions_preview(plan, limit=4):
    """Compact version timeline for catalog cards."""
    today = timezone.localdate()
    rows = []
    for v in plan.versions.all().order_by("-version_number")[:limit]:
        label = v.status
        if v.status == "Published":
            if v.effective_to and v.effective_to < today:
                label = "Expired"
            elif v.effective_from and v.effective_from > today:
                label = "Upcoming"
            else:
                label = "Active"
        elif v.status == "Archived":
            label = "Expired"
        rows.append(
            {
                "version_number": v.version_number,
                "status": v.status,
                "label": label,
                "effective_from": str(v.effective_from) if v.effective_from else None,
                "effective_to": str(v.effective_to) if v.effective_to else None,
            }
        )
    rows.reverse()
    return rows


def filter_plans_by_health(plans_payload_or_ids, health_param, get_health):
    """Filter iterable of plans by health level: healthy|warning|critical."""
    health_param = (health_param or "").strip().lower()
    if not health_param:
        return plans_payload_or_ids
    return [p for p in plans_payload_or_ids if get_health(p) == health_param]


def build_plan_insights(plan, organization=None):
    """Lightweight analytics derived from participants, rates, orders, commissions."""
    from django.db.models import Max, Min, Avg as DjAvg, Sum as DjSum

    from .models import Commission, Order

    version = display_version_for_plan(plan)
    qs = participants_queryset_for_plan(plan, organization)
    employees = qs.count()
    avg_target = qs.aggregate(avg=Avg("personal_target"))["avg"] or Decimal("0")
    coverage = build_coverage_summary(plan, organization)

    top_territories = list(
        qs.filter(territory__isnull=False)
        .values("territory__name")
        .annotate(c=Count("id"))
        .order_by("-c")[:5]
    )
    top_territories = [
        {"name": row["territory__name"], "employees": row["c"]}
        for row in top_territories
        if row["territory__name"]
    ]

    rate_label = "—"
    sample_rate = None
    if version is not None:
        if version.commission_table_type == "FLAT":
            row = version.sc_flat_rate_tables.filter(is_active=True).first()
            if row:
                sample_rate = row.flat_rate
                rate_label = f"Flat {row.flat_rate}%"
        else:
            row = (
                version.sc_rate_tables.filter(is_active=True)
                .order_by("sequence")
                .first()
            )
            if row:
                sample_rate = row.commission_rate
                rate_label = f"{row.tier_name or 'Tier'} @ {row.commission_rate}%"

    projected_monthly = None
    if sample_rate is not None and avg_target:
        projected_monthly = float(
            (Decimal(avg_target) * Decimal(sample_rate) / Decimal("100")).quantize(
                Decimal("0.01")
            )
        )
    projected_annual = (
        round(projected_monthly * 12, 2) if projected_monthly is not None else None
    )
    estimated_monthly_payout = (
        round(projected_monthly * employees, 2)
        if projected_monthly is not None
        else None
    )

    # Actual commissions for this plan (if calculated)
    comm_qs = Commission.objects.filter(compensation_plan=plan)
    if organization is not None:
        comm_qs = comm_qs.filter(organization=organization)
    agg = comm_qs.aggregate(
        avg=DjAvg("commission_amount"),
        hi=Max("commission_amount"),
        lo=Min("commission_amount"),
        total=DjSum("commission_amount"),
    )

    emp_ids = [
        eid
        for eid in qs.exclude(employee_id="")
        .values_list("employee_id", flat=True)
        .distinct()[:2000]
        if eid
    ]
    order_qs = (
        Order.objects.filter(employee_id__in=emp_ids) if emp_ids else Order.objects.none()
    )
    if organization is not None and emp_ids:
        order_qs = order_qs.filter(organization=organization)
    top_products = [
        {"name": row["product_name"], "orders": row["c"]}
        for row in order_qs.exclude(product_name__isnull=True)
        .exclude(product_name="")
        .values("product_name")
        .annotate(c=Count("id"))
        .order_by("-c")[:5]
        if row["product_name"]
    ]

    top_bu = coverage.get("business_units") or []
    top_business_unit = top_bu[0] if top_bu else (plan.business_group or "—")

    # Forecast sparkline: monthly projected for next 6 months (flat heuristic)
    forecast = []
    if projected_monthly is not None:
        for i in range(6):
            forecast.append(
                {
                    "month_offset": i,
                    "projected": projected_monthly,
                }
            )

    return {
        "employees_covered": employees,
        "average_personal_target": float(avg_target) if avg_target else 0,
        "projected_monthly_commission": projected_monthly,
        "projected_annual_commission": projected_annual,
        "estimated_monthly_payout": estimated_monthly_payout,
        "average_commission": float(agg["avg"]) if agg["avg"] is not None else projected_monthly,
        "highest_commission": float(agg["hi"]) if agg["hi"] is not None else None,
        "lowest_commission": float(agg["lo"]) if agg["lo"] is not None else None,
        "average_payout": float(agg["avg"]) if agg["avg"] is not None else projected_monthly,
        "top_territories": top_territories,
        "top_products": top_products,
        "top_business_unit": top_business_unit,
        "most_used_rate_table": rate_label,
        "business_units_covered": coverage.get("business_units") or [],
        "departments_covered": coverage.get("departments") or [],
        "regions_covered": coverage.get("regions") or [],
        "charts": {
            **(coverage.get("charts") or {}),
            "commission_forecast": forecast,
            "plan_usage": {
                "commissions_total": float(agg["total"]) if agg["total"] is not None else 0,
                "employees_covered": employees,
            },
        },
        "calculation_note": (
            "Projections use average personal target × primary rate when live "
            "commission history is limited."
        ),
    }


def plan_activity_queryset(plan, organization=None):
    """Audit events related to this plan (version FK or detail.plan_id)."""
    qs = AuditLog.objects.select_related("user", "plan_version").filter(
        Q(plan_version__compensation_plan_id=plan.id)
        | Q(detail__plan_id=plan.id)
        | Q(detail__plan_id=str(plan.id))
    )
    if organization is not None:
        qs = qs.filter(Q(organization=organization) | Q(organization__isnull=True))
    return qs.order_by("-created_at")


def serialize_activity_row(row):
    label_map = {
        "compensation_plan_created": "Plan Created",
        "compensation_plan_updated": "Plan Updated",
        "plan_version.clone": "Version Cloned",
        "plan_version.publish": "Version Published",
        "plan_version.archive": "Version Archived",
        "plan_version.delete": "Version Deleted",
    }
    detail = row.detail or {}
    # Soft labels for common detail-driven events
    if row.action not in label_map and "rule" in row.action:
        label = "Rule Added"
    elif "quota" in row.action:
        label = "Quota Updated"
    elif "rate" in row.action:
        label = "Rate Changed"
    else:
        label = label_map.get(row.action, row.action.replace("_", " ").replace(".", " ").title())
    return {
        "id": row.id,
        "action": row.action,
        "label": label,
        "user_email": row.user_email or "",
        "detail": detail,
        "plan_version_id": row.plan_version_id,
        "version_number": getattr(row.plan_version, "version_number", None)
        if row.plan_version_id
        else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def build_catalog_summary(organization):
    """Server-side KPI strip for the plan catalog."""
    today = timezone.localdate()
    plans = list(
        _org_plans(organization)
        .prefetch_related(
            Prefetch(
                "versions",
                queryset=CommissionPlanVersion.objects.order_by("-version_number"),
            )
        )
        .order_by("-created_at")
    )

    published_plans = 0
    draft_plans = 0
    archived_only = 0
    active_versions = 0
    upcoming_versions = 0
    expired_versions = 0
    rules_total = 0
    plans_with_rules = 0
    covered_ids = set()
    healthy = 0
    warning = 0
    critical = 0
    score_sum = 0
    attention_plans = []
    plans_ready = 0
    plans_blocked = 0
    pending_approvals = 0
    estimated_monthly_total = 0.0
    buckets = {
        "missing_rules": [],
        "missing_quotas": [],
        "no_participants": [],
        "expires_soon": [],
        "no_rates": [],
    }

    for plan in plans:
        versions = list(plan.versions.all())
        display = display_version_for_plan(plan)
        has_draft = any(v.status == "Draft" for v in versions)
        only_archived = bool(versions) and all(v.status == "Archived" for v in versions)

        if display and display.status == "Published":
            published_plans += 1
        if has_draft:
            draft_plans += 1
        if only_archived:
            archived_only += 1

        for v in versions:
            if v.status == "Published":
                active_versions += 1
                if v.effective_from and v.effective_from > today:
                    upcoming_versions += 1
                if v.effective_to and v.effective_to < today:
                    expired_versions += 1
            elif v.status == "Draft" and v.effective_from and v.effective_from > today:
                upcoming_versions += 1

        if display is not None:
            rc = display.commission_rules.count()
            rules_total += rc
            if rc:
                plans_with_rules += 1

        participant_ids = list(
            participants_queryset_for_plan(plan, organization).values_list("id", flat=True)
        )
        for pid in participant_ids:
            covered_ids.add(pid)

        counts = enrich_plan_card_fields(plan, display)
        components = build_plan_components(plan, display, counts, len(participant_ids))
        warnings = build_plan_warnings(plan, display, counts, len(participant_ids), today)
        health = compute_health_score(components, warnings, display)
        calc_status = build_calculation_status(components, display, health)
        if calc_status["status"] == "ready":
            plans_ready += 1
        elif calc_status["status"] == "blocked":
            plans_blocked += 1
        if calc_status.get("approval_status") == "Pending Approval":
            pending_approvals += 1

        score_sum += health["score"]
        plan_ref = {"id": plan.id, "plan_name": plan.plan_name}
        by_key = {c["key"]: c for c in components}
        if not by_key.get("rules", {}).get("configured"):
            buckets["missing_rules"].append(plan_ref)
        if not by_key.get("monthly_quotas", {}).get("configured"):
            buckets["missing_quotas"].append(plan_ref)
        if not by_key.get("participants", {}).get("configured"):
            buckets["no_participants"].append(plan_ref)
        if not by_key.get("rate_tables", {}).get("configured"):
            buckets["no_rates"].append(plan_ref)
        if any(w["code"] == "expires_soon" for w in warnings):
            buckets["expires_soon"].append(plan_ref)

        if health["level"] == "healthy":
            healthy += 1
        elif health["level"] == "warning":
            warning += 1
            attention_plans.append(_attention_row(plan, health, warnings))
        else:
            critical += 1
            attention_plans.append(_attention_row(plan, health, warnings))

    avg_rules = round(rules_total / len(plans), 1) if plans else 0.0
    avg_readiness = round(score_sum / len(plans), 1) if plans else 0.0
    attention_plans.sort(key=lambda row: row["score"])
    needing_attention = warning + critical

    from django.db.models import Sum
    from .models import Commission

    comm_qs = Commission.objects.all()
    if organization is not None:
        comm_qs = comm_qs.filter(organization=organization)
    commission_generated = float(
        comm_qs.aggregate(total=Sum("commission_amount"))["total"] or 0
    )
    # Indicative monthly run-rate from historical commission totals
    estimated_monthly_total = round(commission_generated / 12.0, 2) if commission_generated else 0.0

    return {
        "published_plans": published_plans,
        "draft_plans": draft_plans,
        "archived_plans": archived_only,
        "employees_covered": len(covered_ids),
        "active_versions": active_versions,
        "upcoming_versions": upcoming_versions,
        "expired_versions": expired_versions,
        "average_rules_per_plan": avg_rules,
        "total_plans": len(plans),
        "healthy_plans": healthy,
        "warning_plans": warning,
        "critical_plans": critical,
        "plans_requiring_attention": needing_attention,
        "average_readiness_score": avg_readiness,
        "attention_plans": attention_plans[:8],
        "action_center": build_action_center_items(buckets),
        "plans_ready_for_calculation": plans_ready,
        "plans_blocked": plans_blocked,
        "pending_approvals": pending_approvals,
        "estimated_monthly_commission": round(estimated_monthly_total, 2),
        "upcoming_effective_changes": upcoming_versions,
    }


def _attention_row(plan, health, warnings):
    return {
        "id": plan.id,
        "plan_name": plan.plan_name,
        "role": plan.role or "",
        "score": health["score"],
        "status": health["status"],
        "level": health["level"],
        "issues": [w["message"] for w in warnings[:4]]
        or [
            c["label"]
            for c in (health.get("contributors") or [])
            if not c.get("ok")
        ][:4],
    }
