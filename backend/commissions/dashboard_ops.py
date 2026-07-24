"""
Sales Compensation Intelligence Dashboard — aggregation helpers.

Does not change commission calculation engines. All queries are tenant-scoped.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum


def _money(value):
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def _delta_pct(curr, prev):
    """Return percent change, or None when comparison is not meaningful."""
    curr_f = _money(curr)
    prev_f = _money(prev)
    if prev_f > 0:
        return round(((curr_f - prev_f) / prev_f) * 100, 1)
    # Do not invent 100% growth when the prior period had no data
    return None


def _kpi_status(delta, unusual=False):
    if unusual:
        return "attention"
    if delta is None:
        return "neutral"
    if abs(float(delta)) < 5:
        return "stable"
    return "up" if float(delta) > 0 else "down"


def _kpi(value, previous=None, **extra):
    curr = _money(value)
    prev = _money(previous) if previous is not None else None
    delta = _delta_pct(curr, prev) if previous is not None else None
    payload = {
        "value": curr,
        "previous": prev,
        "delta_pct": delta,
        "trend": "up" if (delta or 0) > 0 else "down" if (delta or 0) < 0 else "flat",
    }
    payload.update(extra)
    return payload


def attainment_status(pct):
    """Quota bands: Over Achievers / On Track / At Risk / Critical."""
    if pct is None:
        return "unknown", "No Target"
    if pct >= 100:
        return "over_achiever", "Over Achiever"
    if pct >= 75:
        return "on_track", "On Track"
    if pct >= 50:
        return "at_risk", "At Risk"
    return "critical", "Critical"


def _manager_team_employee_ids(profile, organization):
    """Direct reports (+ self) for manager-scoped dashboards."""
    if not profile:
        return []
    from .models import HierarchyRelationship

    qs = HierarchyRelationship.objects.filter(
        parent_participant=profile, is_active=True
    ).select_related("child_participant")
    if organization is not None:
        qs = qs.filter(child_participant__organization=organization)
    eids = [
        (rel.child_participant.employee_id or "").strip()
        for rel in qs
        if rel.child_participant_id
    ]
    if profile.employee_id:
        eids.append(str(profile.employee_id).strip())
    return [e for e in eids if e]


def build_command_center(request):
    """Enterprise Sales Compensation Intelligence payload."""
    from .business_groups import (
        apply_business_group_to_commissions,
        apply_business_group_to_orders,
        normalize_business_group,
        resolve_dashboard_business_group,
    )
    from .currencies import normalize_currency
    from .enterprise_views import (
        _apply_commission_filters,
        _commission_base_queryset,
        _commissions_for_user,
        _profile_display_name,
    )
    from .models import Commission, CompensationPlan, Order, UserProfile
    from .people_ops import resolve_plan_for_profile
    from .permissions import (
        get_request_user_profile,
        user_is_admin,
        user_is_finance,
        user_is_manager,
    )
    from .tenants import filter_queryset_by_organization

    org = getattr(request, "organization", None)
    profile = get_request_user_profile(request)
    is_admin = user_is_admin(request)
    is_finance = user_is_finance(request)
    is_manager = user_is_manager(request)
    can_view_all = is_admin or is_finance
    effective_group, _, _ = resolve_dashboard_business_group(
        request, profile, can_view_all
    )

    # RBAC scope: admin/finance = org; manager = team; else = self
    team_eids = None
    view_mode = "organization"
    if can_view_all:
        view_mode = "organization"
    elif is_manager:
        team_eids = _manager_team_employee_ids(profile, org)
        view_mode = "team"
    else:
        view_mode = "self"
        team_eids = [profile.employee_id] if profile and profile.employee_id else []

    commissions = _commission_base_queryset(request)
    if org:
        commissions = commissions.filter(organization=org)
    if view_mode == "self":
        commissions = _commissions_for_user(request)
    elif view_mode == "team":
        if not team_eids:
            commissions = commissions.none()
        else:
            email_qs = UserProfile.objects.filter(employee_id__in=team_eids)
            if org:
                email_qs = email_qs.filter(organization=org)
            emails = list(email_qs.values_list("email", flat=True))
            commissions = commissions.filter(
                Q(sale__order__employee_id__in=team_eids)
                | Q(employee__email__in=emails)
            )

    commissions, start_date, end_date = _apply_commission_filters(commissions, request)
    commissions = apply_business_group_to_commissions(
        commissions, effective_group, organization=org
    )

    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    period_days = max((end_date - start_date).days + 1, 1)
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    def _prev_commissions_base():
        qs = _commission_base_queryset(request)
        if org:
            qs = qs.filter(organization=org)
        if view_mode == "self":
            qs = _commissions_for_user(request)
        elif view_mode == "team":
            if not team_eids:
                return qs.none()
            email_qs = UserProfile.objects.filter(employee_id__in=team_eids)
            if org:
                email_qs = email_qs.filter(organization=org)
            emails = list(email_qs.values_list("email", flat=True))
            qs = qs.filter(
                Q(sale__order__employee_id__in=team_eids)
                | Q(employee__email__in=emails)
            )
        qs = apply_business_group_to_commissions(qs, effective_group, organization=org)
        return qs.filter(sale__order__order_date__range=[prev_start, prev_end])

    total_liability = commissions.aggregate(t=Sum("commission_amount"))["t"] or 0
    paid = (
        commissions.filter(status=Commission.STATUS_PAID).aggregate(
            t=Sum("commission_amount")
        )["t"]
        or 0
    )
    pending_approval = (
        commissions.filter(
            status__in=[
                getattr(Commission, "STATUS_CALCULATED", "calculated"),
                getattr(Commission, "STATUS_MANAGER_APPROVED", "manager_approved"),
                "calculated",
                "manager_approved",
            ]
        ).aggregate(t=Sum("commission_amount"))["t"]
        or 0
    )
    # Pending = not paid (liability outstanding) for KPI card compatibility
    pending = (
        commissions.exclude(status=Commission.STATUS_PAID).aggregate(
            t=Sum("commission_amount")
        )["t"]
        or 0
    )
    active_participants = commissions.values("employee").distinct().count()

    prev_comms = _prev_commissions_base()
    prev_liability = prev_comms.aggregate(t=Sum("commission_amount"))["t"] or 0
    prev_paid = (
        prev_comms.filter(status=Commission.STATUS_PAID).aggregate(
            t=Sum("commission_amount")
        )["t"]
        or 0
    )
    prev_pending = (
        prev_comms.exclude(status=Commission.STATUS_PAID).aggregate(
            t=Sum("commission_amount")
        )["t"]
        or 0
    )
    prev_participants = prev_comms.values("employee").distinct().count()

    curr = _money(total_liability)
    sales_orders = filter_queryset_by_organization(Order.objects.all(), org)
    sales_orders = sales_orders.filter(order_date__range=[start_date, end_date])
    sales_orders = apply_business_group_to_orders(
        sales_orders, effective_group, organization=org
    )
    if view_mode in ("self", "team"):
        if not team_eids:
            sales_orders = sales_orders.none()
        else:
            sales_orders = sales_orders.filter(employee_id__in=team_eids)

    params = request.query_params
    region = (params.get("region") or "").strip()
    if region:
        sales_orders = sales_orders.filter(region__icontains=region)
        commissions = commissions.filter(sale__order__region__icontains=region)
    territory = (params.get("territory") or "").strip()
    if territory:
        sales_orders = sales_orders.filter(
            Q(territory__name__icontains=territory)
            | Q(territory__code__icontains=territory)
        )
    department = (params.get("department") or "").strip()
    plan_filter = (params.get("plan") or params.get("compensation_plan") or "").strip()
    if plan_filter:
        commissions = commissions.filter(
            Q(compensation_plan__plan_name__icontains=plan_filter)
            | Q(compensation_plan__position_name__icontains=plan_filter)
        )
    employee_q = (params.get("employee") or params.get("q") or "").strip()
    if employee_q:
        sales_orders = sales_orders.filter(
            Q(employee_id__icontains=employee_q)
            | Q(employee_id__iexact=employee_q)
        )
    calc_status = (params.get("calculation_status") or params.get("status") or "").strip()

    total_sales = sales_orders.aggregate(t=Sum("sales_amount"))["t"] or 0
    sales_f = _money(total_sales)
    prev_orders = filter_queryset_by_organization(Order.objects.all(), org)
    prev_orders = prev_orders.filter(order_date__range=[prev_start, prev_end])
    prev_orders = apply_business_group_to_orders(
        prev_orders, effective_group, organization=org
    )
    if view_mode in ("self", "team"):
        if team_eids:
            prev_orders = prev_orders.filter(employee_id__in=team_eids)
        else:
            prev_orders = prev_orders.none()
    if region:
        prev_orders = prev_orders.filter(region__icontains=region)
    prev_sales = _money(prev_orders.aggregate(t=Sum("sales_amount"))["t"] or 0)

    avg_rate = round((curr / sales_f) * 100, 2) if sales_f > 0 else None

    # --- Profiles (team / org scoped) ---
    profiles = filter_queryset_by_organization(
        UserProfile.objects.select_related(
            "territory", "assigned_compensation_plan"
        ).exclude(employee_id=""),
        org,
    )
    if effective_group:
        profiles = profiles.filter(
            business_group__iexact=normalize_business_group(effective_group)
        )
    if department:
        profiles = profiles.filter(department__icontains=department)
    if view_mode in ("self", "team") and team_eids is not None:
        profiles = profiles.filter(employee_id__in=team_eids)
    profiles = list(profiles[:500])
    profile_by_eid = {p.employee_id: p for p in profiles}

    sales_by_emp = {
        row["employee_id"]: row
        for row in sales_orders.values("employee_id").annotate(
            achievement=Sum("sales_amount"),
            order_count=Count("id"),
        )
        if row["employee_id"]
    }
    comm_by_emp = {}
    for row in commissions.values("employee__email", "employee__name").annotate(
        total=Sum("commission_amount")
    ):
        key = (row["employee__email"] or "").lower()
        if key:
            comm_by_emp[key] = _money(row["total"])

    # Plans
    plans = CompensationPlan.objects.all()
    if org:
        plans = plans.filter(organization=org)
    active_plan_qs = plans.filter(status="Active")
    active_plans = active_plan_qs.count()
    blocked = 0
    missing_rules = 0
    pending_plan_approvals = 0
    for plan in active_plan_qs[:200]:
        has_rates = False
        try:
            has_rates = plan.sc_rate_tables.exists() or plan.sc_flat_rate_tables.exists()
        except Exception:
            has_rates = True
        if not has_rates:
            missing_rules += 1
            blocked += 1
        approval = str(getattr(plan, "approval_status", "") or "").lower()
        if approval in ("pending", "in_review"):
            pending_plan_approvals += 1

    # Quota center + attainment distribution
    quota_center = []
    without_plan = 0
    missing_quota = 0
    for p in profiles:
        plan = resolve_plan_for_profile(p, org)
        if not plan:
            without_plan += 1
        sales_row = sales_by_emp.get(p.employee_id) or {}
        achievement = _money(sales_row.get("achievement"))
        quota = _money(p.personal_target)
        if quota <= 0:
            missing_quota += 1
        pct = round((achievement / quota) * 100, 1) if quota > 0 else None
        status_code, status_label = attainment_status(pct)
        email_key = (p.email or "").lower()
        earned = comm_by_emp.get(email_key)
        if earned is None and avg_rate and achievement:
            earned = round(achievement * (avg_rate / 100), 2)
        rate = round(((_money(earned) / achievement) * 100), 2) if achievement > 0 and earned is not None else None
        if achievement <= 0 and quota <= 0:
            continue
        quota_center.append(
            {
                "employee_id": p.employee_id,
                "employee_name": _profile_display_name(p),
                "email": p.email,
                "role": p.role,
                "territory": p.territory.name if p.territory_id else "",
                "department": getattr(p, "department", "") or "",
                "quota": quota,
                "achievement": achievement,
                "attainment_pct": pct,
                "expected_commission": earned,
                "commission_earned": earned,
                "commission_rate": rate,
                "status": status_code,
                "status_label": status_label,
                "currency": normalize_currency(p.personal_currency),
                "plan_name": plan.plan_name if plan else "",
                "plan_id": plan.id if plan else None,
            }
        )
    quota_center.sort(key=lambda r: r["achievement"], reverse=True)

    pcts = [r["attainment_pct"] for r in quota_center if r["attainment_pct"] is not None]
    avg_attainment = round(sum(pcts) / len(pcts), 1) if pcts else None

    # Previous period avg attainment (approx from previous sales vs same quotas)
    prev_sales_by_emp = {
        row["employee_id"]: _money(row["achievement"])
        for row in prev_orders.values("employee_id").annotate(
            achievement=Sum("sales_amount")
        )
        if row["employee_id"]
    }
    prev_pcts = []
    for p in profiles:
        q = _money(p.personal_target)
        if q <= 0:
            continue
        ach = prev_sales_by_emp.get(p.employee_id, 0)
        prev_pcts.append(round((ach / q) * 100, 1))
    prev_avg_attainment = (
        round(sum(prev_pcts) / len(prev_pcts), 1) if prev_pcts else None
    )

    attainment_distribution = {
        "over_achievers": len([r for r in quota_center if r["status"] == "over_achiever"]),
        "on_track": len([r for r in quota_center if r["status"] == "on_track"]),
        "at_risk": len([r for r in quota_center if r["status"] == "at_risk"]),
        "critical": len([r for r in quota_center if r["status"] == "critical"]),
        "unknown": len([r for r in quota_center if r["status"] == "unknown"]),
        "above_quota": len(
            [r for r in quota_center if (r["attainment_pct"] or 0) >= 100]
        ),
        "below_quota": len(
            [
                r
                for r in quota_center
                if r["attainment_pct"] is not None and r["attainment_pct"] < 100
            ]
        ),
    }

    # Forecast: pace current period commission to month end
    today = date.today()
    days_elapsed = max((min(today, end_date) - start_date).days + 1, 1)
    days_total = max((end_date - start_date).days + 1, 1)
    pace = days_total / days_elapsed if days_elapsed else 1
    forecasted = round(curr * pace, 2)
    # Projected payout = last day of end month
    last_day = monthrange(end_date.year, end_date.month)[1]
    projected_payout_date = date(end_date.year, end_date.month, last_day).isoformat()

    # Ops processing pipeline
    orders_imported = sales_orders.count()
    orders_validated = sales_orders.filter(
        order_status__in=["Success", "Booked", "Invoiced"]
    ).count()
    if calc_status:
        # optional filter already applied via commissions path; keep for UI echo
        pass
    calculated_count = commissions.exclude(
        status__in=["", None]
    ).values("sale__order_id").distinct().count()
    if calculated_count == 0:
        calculated_count = commissions.count()
    pending_calcs = sales_orders.filter(order_status="Booked").count()
    if hasattr(Order, "needs_recalculation"):
        pending_calcs = sales_orders.filter(
            Q(needs_recalculation=True) | Q(order_status="Booked")
        ).count()
    payment_ready = commissions.filter(
        status__in=[
            getattr(Commission, "STATUS_APPROVED", "approved"),
            "approved",
            "finance_approved",
        ]
    ).count()
    paid_count = commissions.filter(status=Commission.STATUS_PAID).count()

    success_orders = sales_orders.filter(order_status="Success")
    success_count = success_orders.count()
    with_sale = success_orders.filter(sale_record__isnull=False).count()
    needs_recalc = 0
    if hasattr(Order, "needs_recalculation"):
        needs_recalc = sales_orders.filter(needs_recalculation=True).count()
    orders_without_commission = max(success_count - with_sale, 0)
    leakage_count = orders_without_commission + needs_recalc + without_plan + missing_quota
    leakage_risk = (
        "high" if leakage_count >= 10 else "medium" if leakage_count >= 3 else "low"
    )

    # Expired plan versions
    expired_versions = 0
    try:
        from .models import CommissionPlanVersion

        ver_qs = CommissionPlanVersion.objects.filter(
            status=CommissionPlanVersion.STATUS_PUBLISHED,
            effective_to__lt=today,
        )
        if org:
            ver_qs = ver_qs.filter(organization=org)
        expired_versions = ver_qs.count()
        leakage_count += expired_versions
    except Exception:
        expired_versions = 0

    # Plan performance ROI
    plan_by_profile = {}
    for p in profiles:
        rp = resolve_plan_for_profile(p, org)
        if rp:
            plan_by_profile.setdefault(rp.id, []).append(p.employee_id)

    plan_performance = []
    for plan in active_plan_qs[:50]:
        plan_comms = commissions.filter(compensation_plan=plan)
        comm_cost = _money(plan_comms.aggregate(t=Sum("commission_amount"))["t"] or 0)
        covered_eids = plan_by_profile.get(plan.id, [])
        rev = _money(
            sales_orders.filter(employee_id__in=covered_eids).aggregate(
                t=Sum("sales_amount")
            )["t"]
            or 0
        )
        ratio = round((comm_cost / rev) * 100, 2) if rev > 0 else None
        roi = round(rev / comm_cost, 2) if comm_cost > 0 else None
        plan_performance.append(
            {
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "employees_covered": len(covered_eids),
                "revenue_generated": rev,
                "commission_cost": comm_cost,
                "commission_ratio_pct": ratio,
                "roi": roi,
                "roi_label": f"{roi}x" if roi is not None else "—",
                "status": (
                    "Needs Review"
                    if (roi is not None and roi < 1) or (rev == 0 and comm_cost > 0)
                    else "Healthy"
                    if roi is not None and roi >= 3
                    else "Monitor"
                ),
            }
        )
    plan_performance.sort(key=lambda r: r["revenue_generated"], reverse=True)

    # Territory analytics
    territory_rows = []
    terr_agg = (
        sales_orders.values("territory__name", "region")
        .annotate(sales=Sum("sales_amount"), orders=Count("id"))
        .order_by("-sales")[:20]
    )
    quota_by_terr = {}
    for p in profiles:
        tname = p.territory.name if p.territory_id else "Unspecified"
        quota_by_terr[tname] = quota_by_terr.get(tname, 0) + _money(p.personal_target)
    for row in terr_agg:
        tname = (row["territory__name"] or "").strip() or "Unspecified"
        sales_v = _money(row["sales"])
        q = quota_by_terr.get(tname, 0)
        pct = round((sales_v / q) * 100, 1) if q > 0 else None
        territory_rows.append(
            {
                "territory": tname,
                "region": (row["region"] or "").strip() or "—",
                "sales": sales_v,
                "quota": q,
                "attainment_pct": pct,
                "order_count": row["orders"],
            }
        )

    # Enrich territories with commission % and period growth
    prev_terr = {
        ((r["territory__name"] or "").strip() or "Unspecified"): _money(r["sales"])
        for r in prev_orders.values("territory__name")
        .annotate(sales=Sum("sales_amount"))
    }
    terr_comm = {
        ((r["sale__order__territory__name"] or "").strip() or "Unspecified"): _money(
            r["total"]
        )
        for r in commissions.values("sale__order__territory__name").annotate(
            total=Sum("commission_amount")
        )
    }
    for row in territory_rows:
        tname = row["territory"]
        c_amt = terr_comm.get(tname, 0)
        row["commission"] = c_amt
        row["commission_pct"] = (
            round((c_amt / row["sales"]) * 100, 2) if row["sales"] > 0 else None
        )
        prev_s = prev_terr.get(tname, 0)
        row["growth_pct"] = _delta_pct(row["sales"], prev_s)
    territory_rows.sort(key=lambda r: r["sales"], reverse=True)

    # Revenue vs commission trend
    rev_comm = []
    cursor = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while cursor <= end_month:
        if cursor.month == 12:
            next_m = date(cursor.year + 1, 1, 1)
        else:
            next_m = date(cursor.year, cursor.month + 1, 1)
        m_end = next_m - timedelta(days=1)
        range_end = min(m_end, end_date)
        range_start = max(cursor, start_date)
        m_sales = (
            sales_orders.filter(order_date__range=[range_start, range_end]).aggregate(
                t=Sum("sales_amount")
            )["t"]
            or 0
        )
        m_comm = (
            commissions.filter(
                sale__order__order_date__range=[range_start, range_end]
            ).aggregate(t=Sum("commission_amount"))["t"]
            or 0
        )
        m_paid = (
            commissions.filter(
                status=Commission.STATUS_PAID,
                sale__order__order_date__range=[range_start, range_end],
            ).aggregate(t=Sum("commission_amount"))["t"]
            or 0
        )
        s = _money(m_sales)
        c = _money(m_comm)
        pmt = _money(m_paid)
        rev_comm.append(
            {
                "period": cursor.strftime("%Y-%m"),
                "label": cursor.strftime("%b %Y"),
                "sales": s,
                "revenue": s,
                "commission": c,
                "payout": pmt,
                "quota": round(s / (avg_attainment / 100), 2)
                if avg_attainment and avg_attainment > 0
                else None,
                "margin": round(s - c, 2),
                "commission_pct": round((c / s) * 100, 2) if s > 0 else None,
            }
        )
        cursor = next_m

    leakage_issues = [
        {
            "code": "orders_without_commission",
            "title": "Orders without commission",
            "count": orders_without_commission,
            "severity": "high" if orders_without_commission else "low",
            "href": "/orders?order_status=Success",
        },
        {
            "code": "employees_without_plans",
            "title": "Employees without active plans",
            "count": without_plan,
            "severity": "medium" if without_plan else "low",
            "href": "/user-setup",
        },
        {
            "code": "missing_quota",
            "title": "Missing quota",
            "count": missing_quota,
            "severity": "medium" if missing_quota else "low",
            "href": "/user-setup",
        },
        {
            "code": "calculation_failures",
            "title": "Calculation failures / recalc needed",
            "count": needs_recalc,
            "severity": "high" if needs_recalc else "low",
            "href": "/orders",
        },
        {
            "code": "expired_versions",
            "title": "Expired compensation versions",
            "count": expired_versions,
            "severity": "medium" if expired_versions else "low",
            "href": "/comp-plans",
        },
    ]
    leakage_issues = [i for i in leakage_issues if i["count"] > 0]

    # Extra ops signals for Action Center / Operational Health
    failed_imports = 0
    try:
        from .models import ImportJob

        ij = ImportJob.objects.filter(status=ImportJob.STATUS_FAILED)
        if org:
            ij = ij.filter(organization=org)
        failed_imports = ij.count()
    except Exception:
        failed_imports = 0

    failed_calcs = commissions.filter(status=Commission.STATUS_FAILED).count()
    blocked_payouts = 0
    try:
        from .models import PayoutRun

        pr = PayoutRun.objects.filter(status=PayoutRun.STATUS_DRAFT)
        if org:
            pr = pr.filter(organization=org)
        blocked_payouts = pr.count()
    except Exception:
        blocked_payouts = 0

    plans_expiring = 0
    try:
        horizon = today + timedelta(days=30)
        pe = active_plan_qs.filter(
            effective_end_date__isnull=False,
            effective_end_date__gte=today,
            effective_end_date__lte=horizon,
        )
        plans_expiring = pe.count()
    except Exception:
        plans_expiring = 0

    pending_approvals_count = commissions.filter(
        status__in=["calculated", "manager_approved"]
    ).count()

    leakage_impact = round(
        _money(
            success_orders.filter(sale_record__isnull=True).aggregate(
                t=Sum("sales_amount")
            )["t"]
            or 0
        )
        * 0.05,
        2,
    )

    action_center = [
        {
            "code": "revenue_leakage",
            "title": "Revenue leakage",
            "subtitle": "%s affected orders" % orders_without_commission,
            "count": leakage_count,
            "severity": "high" if leakage_risk == "high" else "medium",
            "severity_rank": 1 if leakage_risk == "high" else 2,
            "action_label": "Review",
            "href": "/orders",
            "impact_label": "Potential delayed payout",
            "impact_amount": leakage_impact,
        },
        {
            "code": "pending_approvals",
            "title": "Pending approvals",
            "subtitle": "%s commission batches" % pending_approvals_count,
            "count": pending_approvals_count,
            "severity": "high" if pending_approvals_count >= 20 else "medium",
            "severity_rank": 1 if pending_approvals_count >= 20 else 2,
            "action_label": "Review",
            "href": "/commissions",
            "impact_label": "Pending liability",
            "impact_amount": _money(pending_approval),
        },
        {
            "code": "failed_calculations",
            "title": "Failed calculations",
            "subtitle": "%s calculation issues" % (failed_calcs + needs_recalc),
            "count": failed_calcs + needs_recalc,
            "severity": "high",
            "severity_rank": 1,
            "action_label": "Review",
            "href": "/commissions",
            "impact_label": None,
            "impact_amount": None,
        },
        {
            "code": "failed_imports",
            "title": "Failed imports",
            "subtitle": "%s import jobs" % failed_imports,
            "count": failed_imports,
            "severity": "high",
            "severity_rank": 1,
            "action_label": "Open",
            "href": "/orders",
            "impact_label": None,
            "impact_amount": None,
        },
        {
            "code": "plans_expiring",
            "title": "Plans expiring",
            "subtitle": "%s plans within 30 days" % plans_expiring,
            "count": plans_expiring,
            "severity": "medium",
            "severity_rank": 2,
            "action_label": "Open",
            "href": "/comp-plans",
            "impact_label": None,
            "impact_amount": None,
        },
        {
            "code": "blocked_payouts",
            "title": "Blocked payouts",
            "subtitle": "%s draft payout runs" % blocked_payouts,
            "count": blocked_payouts,
            "severity": "high" if blocked_payouts else "medium",
            "severity_rank": 1 if blocked_payouts else 2,
            "action_label": "Open",
            "href": "/payouts",
            "impact_label": "Held commissions",
            "impact_amount": _money(pending),
        },
        {
            "code": "missing_quota",
            "title": "Quota configuration",
            "subtitle": "%s missing quotas" % missing_quota,
            "count": missing_quota,
            "severity": "low",
            "severity_rank": 3,
            "action_label": "Configure",
            "href": "/user-setup",
            "impact_label": None,
            "impact_amount": None,
        },
    ]
    action_center = [a for a in action_center if a["count"] > 0]
    action_center.sort(key=lambda a: (a.get("severity_rank", 9), -a.get("count", 0)))

    def _health_score(issue_count, weight=5):
        return max(0, min(100, round(100 - issue_count * weight)))

    operational_health = {
        "risk": leakage_risk,
        "scorecards": [
            {
                "code": "configuration",
                "label": "Configuration Health",
                "score": _health_score(missing_rules + without_plan + missing_quota, 8),
                "status": (
                    "healthy"
                    if (missing_rules + without_plan + missing_quota) == 0
                    else "attention"
                    if (missing_rules + without_plan + missing_quota) < 5
                    else "critical"
                ),
                "trend": "flat",
                "href": "/comp-plans",
            },
            {
                "code": "calculation",
                "label": "Calculation Health",
                "score": _health_score(failed_calcs + needs_recalc, 12),
                "status": (
                    "healthy"
                    if (failed_calcs + needs_recalc) == 0
                    else "attention"
                    if (failed_calcs + needs_recalc) < 3
                    else "critical"
                ),
                "trend": "flat",
                "href": "/commissions",
            },
            {
                "code": "approval",
                "label": "Approval Health",
                "score": _health_score(pending_approvals_count, 2),
                "status": (
                    "healthy"
                    if pending_approvals_count == 0
                    else "attention"
                    if pending_approvals_count < 10
                    else "critical"
                ),
                "trend": "flat",
                "href": "/commissions",
            },
            {
                "code": "payroll",
                "label": "Payroll Readiness",
                "score": _health_score(
                    blocked_payouts + (1 if pending_approvals_count else 0), 15
                ),
                "status": (
                    "healthy"
                    if blocked_payouts == 0 and pending_approvals_count < 5
                    else "attention"
                ),
                "trend": "flat",
                "href": "/payouts",
            },
            {
                "code": "crm_sync",
                "label": "CRM Sync Health",
                "score": 100 if failed_imports == 0 else _health_score(failed_imports, 25),
                "status": "healthy" if failed_imports == 0 else "critical",
                "status_label": "Healthy" if failed_imports == 0 else "Issues detected",
                "trend": "flat",
                "href": "/integrations",
            },
        ],
        "items": [
            {
                "code": "configuration",
                "label": "Configuration issues",
                "count": missing_rules + without_plan,
                "href": "/comp-plans",
            },
            {
                "code": "leakage",
                "label": "Revenue leakage",
                "count": orders_without_commission + missing_quota,
                "href": "/orders",
            },
            {
                "code": "pending_approvals",
                "label": "Pending approvals",
                "count": pending_approvals_count,
                "href": "/commissions",
            },
            {
                "code": "calculation_errors",
                "label": "Calculation errors",
                "count": failed_calcs + needs_recalc,
                "href": "/commissions",
            },
            {
                "code": "blocked_plans",
                "label": "Blocked plans",
                "count": blocked,
                "href": "/comp-plans",
            },
            {
                "code": "expiring_versions",
                "label": "Expiring versions",
                "count": expired_versions + plans_expiring,
                "href": "/comp-plans",
            },
        ],
    }

    ops_alerts = [
        {
            "code": "pending_calcs",
            "title": "Commission Calculations Pending",
            "count": pending_calcs,
            "severity": "medium" if pending_calcs else "low",
            "action_label": "Review",
            "href": "/orders?order_status=Booked",
        },
        {
            "code": "missing_rules",
            "title": "Plans Missing Rules",
            "count": missing_rules,
            "severity": "high" if missing_rules else "low",
            "action_label": "Fix",
            "href": "/comp-plans",
        },
        {
            "code": "without_plans",
            "title": "Employees Without Plans",
            "count": without_plan,
            "severity": "medium" if without_plan else "low",
            "action_label": "Review",
            "href": "/user-setup",
        },
        {
            "code": "leakage",
            "title": "Revenue Leakage Risk",
            "count": leakage_count,
            "severity": "high" if leakage_risk == "high" else "medium",
            "action_label": "Fix Now",
            "href": "/orders?order_status=Success",
        },
    ]

    top_earners = list(
        commissions.values("employee__name", "employee__email")
        .annotate(total=Sum("commission_amount"), count=Count("id"))
        .order_by("-total")[:8]
    )
    highest_revenue = []
    for eid, row in sales_by_emp.items():
        p = profile_by_eid.get(eid)
        highest_revenue.append(
            {
                "employee_id": eid,
                "employee_name": _profile_display_name(p) if p else eid,
                "sales": _money(row.get("achievement")),
            }
        )
    highest_revenue.sort(key=lambda x: x["sales"], reverse=True)
    highest_revenue = highest_revenue[:8]

    largest_deals = list(
        sales_orders.order_by("-sales_amount").values(
            "order_id", "employee_id", "sales_amount", "order_date", "region"
        )[:8]
    )

    top_performers = []
    for idx, row in enumerate(quota_center[:25], start=1):
        top_performers.append(
            {
                "rank": idx,
                "employee_id": row["employee_id"],
                "employee_name": row["employee_name"],
                "territory": row["territory"],
                "sales_revenue": row["achievement"],
                "quota": row["quota"],
                "attainment_pct": row["attainment_pct"],
                "commission_earned": row["commission_earned"],
                "commission_rate": row["commission_rate"],
                "currency": row["currency"],
                "status": row["status"],
                "status_label": row["status_label"],
            }
        )

    # Manager team summary
    team_summary = None
    if view_mode == "team":
        team_summary = {
            "team_size": len(team_eids or []),
            "sales_achieved": sales_f,
            "quota_attainment": avg_attainment,
            "commission_earned": curr,
            "pending_actions": pending_calcs + len(leakage_issues),
        }

    kpis_structured = {
        "total_sales": _kpi(sales_f, prev_sales),
        "commission_liability": _kpi(curr, prev_liability),
        "commission_paid": _kpi(paid, prev_paid),
        "commission_pending_approval": _kpi(pending_approval, None),
        "commission_pending": _kpi(pending, prev_pending),
        "forecasted_commission": _kpi(forecasted, curr),
        "average_attainment": {
            "value": avg_attainment,
            "previous": prev_avg_attainment,
            "delta_pct": _delta_pct(avg_attainment or 0, prev_avg_attainment or 0)
            if avg_attainment is not None and prev_avg_attainment is not None
            else None,
            "trend": "up"
            if (avg_attainment or 0) > (prev_avg_attainment or 0)
            else "down"
            if (avg_attainment or 0) < (prev_avg_attainment or 0)
            else "flat",
            "unit": "percent",
        },
        "active_compensation_plans": _kpi(active_plans, None),
        "employees_receiving_commission": _kpi(
            active_participants, prev_participants
        ),
        "quota_attainment": avg_attainment,
        "active_participants": active_participants,
        "avg_commission_rate": avg_rate,
        "leakage_risk": leakage_risk,
        "leakage_count": leakage_count,
        "liability_delta_pct": _delta_pct(curr, prev_liability),
    }

    spark_sales = [r["sales"] for r in rev_comm][-6:]
    spark_comm = [r["commission"] for r in rev_comm][-6:]
    spark_paid = [r["payout"] for r in rev_comm][-6:]

    def _unusual(delta):
        if delta is None:
            return False
        return abs(float(delta)) >= 15

    sales_delta = _delta_pct(sales_f, prev_sales)
    liability_delta = _delta_pct(curr, prev_liability)
    paid_delta = _delta_pct(paid, prev_paid)
    attain_delta = kpis_structured["average_attainment"]["delta_pct"]

    risk_label = (
        "High" if leakage_risk == "high" else "Medium" if leakage_risk == "medium" else "Low"
    )
    risk_rank = {"high": 3, "medium": 2, "low": 1}.get(leakage_risk, 1)

    # Composite Business Health Score (0–100)
    scorecards = operational_health.get("scorecards") or []
    score_map = {c["code"]: c.get("score", 70) for c in scorecards}
    revenue_score = (
        90
        if sales_delta is not None and sales_delta >= 5
        else 75
        if sales_delta is not None and sales_delta >= 0
        else 55
        if sales_delta is not None
        else (80 if sales_f > 0 else 50)
    )
    quota_score = (
        min(100, int(avg_attainment))
        if avg_attainment is not None
        else score_map.get("configuration", 70)
    )
    commission_score = score_map.get("calculation", 70)
    plans_score = score_map.get("configuration", 70)
    approvals_score = score_map.get("approval", 70)
    business_health_score = int(
        round(
            revenue_score * 0.25
            + quota_score * 0.25
            + commission_score * 0.2
            + plans_score * 0.15
            + approvals_score * 0.15
        )
    )
    business_health = {
        "score": max(0, min(100, business_health_score)),
        "label": (
            "Strong"
            if business_health_score >= 80
            else "Stable"
            if business_health_score >= 65
            else "At Risk"
            if business_health_score >= 45
            else "Critical"
        ),
        "components": [
            {"code": "revenue", "label": "Revenue", "score": revenue_score},
            {"code": "quota", "label": "Quota", "score": int(quota_score)},
            {"code": "commission", "label": "Commission", "score": commission_score},
            {"code": "plans", "label": "Plans", "score": plans_score},
            {"code": "approvals", "label": "Approvals", "score": approvals_score},
        ],
    }

    def _ctx(delta):
        return "vs previous period" if delta is not None else "Current period"

    executive_kpis = [
        {
            "key": "revenue",
            "label": "Revenue",
            "value": sales_f,
            "format": "money",
            "delta_pct": sales_delta,
            "unusual": _unusual(sales_delta),
            "status": _kpi_status(sales_delta, _unusual(sales_delta)),
            "explanation": _ctx(sales_delta),
            "sparkline": spark_sales,
            "href": "/orders",
        },
        {
            "key": "liability",
            "label": "Commission Liability",
            "value": curr,
            "format": "money",
            "delta_pct": liability_delta,
            "unusual": _unusual(liability_delta),
            "status": _kpi_status(liability_delta, _unusual(liability_delta)),
            "explanation": _ctx(liability_delta),
            "sparkline": spark_comm,
            "href": "/commissions",
        },
        {
            "key": "paid",
            "label": "Paid",
            "value": _money(paid),
            "format": "money",
            "delta_pct": paid_delta,
            "unusual": _unusual(paid_delta),
            "status": _kpi_status(paid_delta, _unusual(paid_delta)),
            "explanation": _ctx(paid_delta),
            "sparkline": spark_paid,
            "href": "/payouts",
        },
        {
            "key": "forecast",
            "label": "Forecast",
            "value": forecasted,
            "format": "money",
            "delta_pct": None,
            "unusual": False,
            "status": "neutral",
            "explanation": "Current period",
            "sparkline": spark_comm,
            "href": "/commissions",
        },
        {
            "key": "attainment",
            "label": "Quota Attainment",
            "value": avg_attainment,
            "format": "percent",
            "delta_pct": attain_delta,
            "unusual": _unusual(attain_delta),
            "status": _kpi_status(attain_delta, _unusual(attain_delta)),
            "explanation": _ctx(attain_delta),
            "sparkline": [],
            "href": "/user-setup",
        },
        {
            "key": "risk",
            "label": "Risk Score",
            "value": risk_label,
            "format": "text",
            "delta_pct": None,
            "unusual": leakage_risk == "high",
            "status": (
                "attention"
                if leakage_risk == "high"
                else "down"
                if leakage_risk == "medium"
                else "stable"
            ),
            "explanation": "Current period",
            "sparkline": [],
            "href": "/commissions",
            "risk_rank": risk_rank,
        },
    ]

    by_roi = sorted(
        [p for p in plan_performance if p.get("roi") is not None],
        key=lambda p: p["roi"],
        reverse=True,
    )
    by_cost = sorted(plan_performance, key=lambda p: p["commission_cost"], reverse=True)
    by_rev = sorted(plan_performance, key=lambda p: p["revenue_generated"], reverse=True)
    # Approximate lowest attainment via commission ratio (higher cost/revenue = weaker ROI)
    by_weak = sorted(
        [p for p in plan_performance if p.get("commission_ratio_pct") is not None],
        key=lambda p: p["commission_ratio_pct"],
        reverse=True,
    )
    plan_cohorts = {
        "top_performing": by_rev[:3],
        "highest_cost": by_cost[:3],
        "highest_roi": by_roi[:3],
        "lowest_attainment": by_weak[:3],
        "highest_growth": by_rev[:3],  # growth proxy: current revenue leaders
    }

    territory_board = {
        "top": territory_rows[:5],
        "worst": sorted(territory_rows, key=lambda r: r["sales"])[:5],
    }

    executive_insights = []
    if sales_delta is not None:
        executive_insights.append(
            {
                "code": "revenue_change",
                "title": "Revenue Trend",
                "text": "Revenue %s %s%%"
                % ("increased" if sales_delta >= 0 else "decreased", abs(sales_delta)),
                "tone": "positive" if sales_delta >= 0 else "caution",
                "cta": "View Orders",
                "href": "/orders",
            }
        )
    attention_plans = blocked + plans_expiring + missing_rules
    if attention_plans:
        executive_insights.append(
            {
                "code": "plans_attention",
                "title": "Compensation Risk",
                "text": "%s plans require review" % attention_plans,
                "tone": "caution",
                "cta": "Review Plans",
                "href": "/comp-plans",
            }
        )
    weak_terr = [
        t
        for t in territory_rows
        if t.get("attainment_pct") is not None and t["attainment_pct"] < 50
    ]
    if weak_terr:
        executive_insights.append(
            {
                "code": "territory_under",
                "title": "Quota Risk",
                "text": "%s territor%s below target"
                % (len(weak_terr), "y" if len(weak_terr) == 1 else "ies"),
                "tone": "caution",
                "cta": "View Territories",
                "href": "/analytics/reports",
            }
        )
    over = attainment_distribution.get("over_achievers") or 0
    if over:
        executive_insights.append(
            {
                "code": "over_achievers",
                "title": "Quota Strength",
                "text": "%s employees above target" % over,
                "tone": "positive",
                "cta": "Open People",
                "href": "/user-setup",
            }
        )
    if avg_rate is not None:
        executive_insights.append(
            {
                "code": "commission_cost",
                "title": "Commission Cost",
                "text": "Cost ratio at %s%%" % avg_rate,
                "tone": "positive" if avg_rate < 5 else "caution" if avg_rate < 12 else "critical",
                "cta": "Open Commissions",
                "href": "/commissions",
            }
        )
    if not executive_insights:
        executive_insights.append(
            {
                "code": "stable",
                "title": "Performance",
                "text": "Stable for selected period",
                "tone": "neutral",
                "cta": "Open Analytics",
                "href": "/analytics",
            }
        )

    BUSINESS_ACTIVITY_PREFIXES = (
        "commission",
        "commissions_",
        "payout",
        "payroll",
        "crm_",
        "integration_",
        "compensation_plan",
        "plan_version",
        "quota_",
        "order_",
        "orders_",
        "field_mapping",
        "ai_compensation",
        "report_exported",
        "sync",
    )
    BUSINESS_ACTIVITY_BLOCK = (
        "login",
        "logout",
        "signed",
        "session",
        "mfa_",
        "password",
        "invite_",
        "profile_updated",
        "report_viewed",
        "people_profile",
        "trusted_device",
    )

    recent_activity = []
    try:
        from .models import AuditLog
        from .audit_catalog import action_label

        audit_qs = AuditLog.objects.all().order_by("-created_at")
        if org is not None:
            audit_qs = audit_qs.filter(organization=org)
        for row in audit_qs[:60]:
            action = str(row.action or "")
            low = action.lower()
            if any(low.startswith(b) or b in low for b in BUSINESS_ACTIVITY_BLOCK):
                continue
            if not any(low.startswith(p) for p in BUSINESS_ACTIVITY_PREFIXES):
                continue
            recent_activity.append(
                {
                    "id": row.id,
                    "at": row.created_at.isoformat() if row.created_at else None,
                    "label": action_label(row.action) or row.action,
                    "action": row.action,
                    "severity": row.severity or "info",
                }
            )
            if len(recent_activity) >= 8:
                break
    except Exception:
        recent_activity = []

    from django.utils import timezone as dj_tz

    generated_at = dj_tz.now().isoformat()
    operational_health["evaluated_at"] = generated_at

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "previous_start_date": str(prev_start),
        "previous_end_date": str(prev_end),
        "business_group": effective_group or "all",
        "view_mode": view_mode,
        "generated_at": generated_at,
        "kpis": {
            "total_sales": sales_f,
            "commission_liability": curr,
            "commission_paid": _money(paid),
            "commission_pending": _money(pending),
            "commission_pending_approval": _money(pending_approval),
            "forecasted_commission": forecasted,
            "quota_attainment": avg_attainment,
            "active_plans": active_plans,
            "active_participants": active_participants,
            "employees_receiving_commission": active_participants,
            "avg_commission_rate": avg_rate,
            "leakage_risk": leakage_risk,
            "leakage_count": leakage_count,
            "liability_delta_pct": liability_delta,
            "sales_delta_pct": sales_delta,
            "paid_delta_pct": paid_delta,
            "pending_delta_pct": _delta_pct(pending, prev_pending),
            "attainment_delta_pct": attain_delta,
            "participants_delta_pct": _delta_pct(
                active_participants, prev_participants
            ),
        },
        "executive_kpis": executive_kpis,
        "business_health": business_health,
        "kpi_cards": kpis_structured,
        "processing_status": {
            "orders_imported": orders_imported,
            "orders_validated": orders_validated,
            "calculations_completed": calculated_count,
            "pending_approvals": pending_approvals_count,
            "payment_ready": payment_ready,
            "paid": paid_count,
            "pending_calculations": pending_calcs,
        },
        "forecast": {
            "projected_monthly_commission": forecasted,
            "projected_payout_date": projected_payout_date,
            "pace_factor": round(pace, 3),
            "basis": "period_to_date_run_rate",
        },
        "attainment_distribution": attainment_distribution,
        "plan_performance": plan_performance,
        "plan_cohorts": plan_cohorts,
        "top_performers": top_performers,
        "leakage": {
            "risk": leakage_risk,
            "total_issues": leakage_count,
            "issues": leakage_issues,
        },
        "action_center": action_center,
        "operational_health": operational_health,
        "executive_insights": executive_insights,
        "recent_activity": recent_activity,
        "team_summary": team_summary,
        "plan_health": {
            "active_plans": active_plans,
            "blocked_plans": blocked,
            "missing_rules": missing_rules,
            "pending_approvals": pending_plan_approvals,
        },
        "ops_alerts": ops_alerts,
        "quota_center": quota_center[:50],
        "territory_analytics": territory_rows,
        "territory_board": territory_board,
        "revenue_vs_commission": rev_comm,
        "trend_series": rev_comm,
        "commission_trend": [
            {"period": r["period"], "label": r["label"], "value": r["commission"]}
            for r in rev_comm
        ],
        "insights": {
            "top_earners": [
                {
                    "name": r["employee__name"] or r["employee__email"],
                    "email": r["employee__email"],
                    "total": _money(r["total"]),
                    "count": r["count"],
                }
                for r in top_earners
            ],
            "highest_revenue": highest_revenue,
            "largest_deals": [
                {
                    "order_id": d["order_id"],
                    "employee_id": d["employee_id"],
                    "sales_amount": _money(d["sales_amount"]),
                    "order_date": d["order_date"].isoformat()
                    if d["order_date"]
                    else None,
                    "region": d.get("region") or "",
                }
                for d in largest_deals
            ],
        },
    }
