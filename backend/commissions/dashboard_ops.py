"""
Sales Compensation Command Center — aggregation helpers.

Does not change commission calculation engines.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum


def _money(value):
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def attainment_status(pct):
    if pct is None:
        return "unknown", "No Target"
    if pct >= 100:
        return "exceeded", "Exceeded"
    if pct >= 85:
        return "on_track", "On Track"
    if pct >= 60:
        return "at_risk", "At Risk"
    return "below", "Below Target"


def build_command_center(request):
    """Aggregate KPIs, health, ops alerts, quota center, territory analytics."""
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
        user_can_view_finance_data,
        user_is_admin,
        user_is_finance,
        user_is_manager,
    )
    from .tenants import filter_queryset_by_organization

    org = getattr(request, "organization", None)
    profile = get_request_user_profile(request)
    can_view_all = user_is_admin(request) or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, profile, can_view_all
    )

    commissions = _commission_base_queryset(request)
    if org:
        commissions = commissions.filter(organization=org)
    scoped = not user_can_view_finance_data(request) and not user_is_manager(request)
    if scoped:
        commissions = _commissions_for_user(request)
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

    total_liability = commissions.aggregate(t=Sum("commission_amount"))["t"] or 0
    paid = (
        commissions.filter(status=Commission.STATUS_PAID).aggregate(
            t=Sum("commission_amount")
        )["t"]
        or 0
    )
    pending = (
        commissions.exclude(status=Commission.STATUS_PAID).aggregate(
            t=Sum("commission_amount")
        )["t"]
        or 0
    )
    active_participants = commissions.values("employee").distinct().count()

    prev_comms = _commission_base_queryset(request)
    if org:
        prev_comms = prev_comms.filter(organization=org)
    if scoped:
        prev_comms = _commissions_for_user(request)
    prev_comms = apply_business_group_to_commissions(
        prev_comms, effective_group, organization=org
    )
    prev_comms = prev_comms.filter(
        sale__order__order_date__range=[prev_start, prev_end]
    )
    prev_liability = prev_comms.aggregate(t=Sum("commission_amount"))["t"] or 0

    curr = _money(total_liability)
    prev = _money(prev_liability)
    liability_delta_pct = (
        round(((curr - prev) / prev) * 100, 1) if prev > 0 else None
    )

    orders = filter_queryset_by_organization(Order.objects.all(), org)
    orders = orders.filter(order_date__range=[start_date, end_date])
    orders = apply_business_group_to_orders(orders, effective_group, organization=org)
    if scoped and profile and profile.employee_id:
        orders = orders.filter(employee_id=profile.employee_id)
    elif scoped:
        orders = orders.none()

    params = request.query_params
    region = (params.get("region") or "").strip()
    if region:
        orders = orders.filter(region__icontains=region)
        commissions = commissions.filter(sale__order__region__icontains=region)
    territory = (params.get("territory") or "").strip()
    if territory:
        orders = orders.filter(
            Q(territory__name__icontains=territory)
            | Q(territory__code__icontains=territory)
        )
    plan_filter = (params.get("plan") or params.get("compensation_plan") or "").strip()
    if plan_filter:
        commissions = commissions.filter(
            Q(compensation_plan__plan_name__icontains=plan_filter)
            | Q(compensation_plan__position_name__icontains=plan_filter)
        )
    employee_q = (params.get("employee") or params.get("q") or "").strip()
    if employee_q:
        orders = orders.filter(employee_id__icontains=employee_q)

    total_sales = orders.aggregate(t=Sum("sales_amount"))["t"] or 0
    sales_f = _money(total_sales)
    avg_rate = round((curr / sales_f) * 100, 2) if sales_f > 0 else None

    success_orders = orders.filter(order_status="Success")
    success_count = success_orders.count()
    with_sale = success_orders.filter(sale_record__isnull=False).count()
    needs_recalc = 0
    if hasattr(Order, "needs_recalculation"):
        needs_recalc = orders.filter(needs_recalculation=True).count()
    leakage_count = max(success_count - with_sale, 0) + needs_recalc
    leakage_risk = (
        "high" if leakage_count >= 10 else "medium" if leakage_count >= 3 else "low"
    )

    plans = CompensationPlan.objects.all()
    if org:
        plans = plans.filter(organization=org)
    active_plans = plans.filter(status="Active").count()
    blocked = 0
    missing_rules = 0
    pending_approvals = 0
    for plan in plans.filter(status="Active")[:200]:
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
            pending_approvals += 1

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
    profiles = list(profiles[:500])
    profile_by_eid = {p.employee_id: p for p in profiles}

    sales_by_emp = {
        row["employee_id"]: row
        for row in orders.values("employee_id").annotate(
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

    quota_center = []
    without_plan = 0
    for p in profiles:
        plan = resolve_plan_for_profile(p, org)
        if not plan:
            without_plan += 1
        sales_row = sales_by_emp.get(p.employee_id) or {}
        achievement = _money(sales_row.get("achievement"))
        quota = _money(p.personal_target)
        pct = round((achievement / quota) * 100, 1) if quota > 0 else None
        status_code, status_label = attainment_status(pct)
        email_key = (p.email or "").lower()
        expected = comm_by_emp.get(email_key)
        if expected is None and avg_rate and achievement:
            expected = round(achievement * (avg_rate / 100), 2)
        if achievement <= 0 and quota <= 0:
            continue
        quota_center.append(
            {
                "employee_id": p.employee_id,
                "employee_name": _profile_display_name(p),
                "email": p.email,
                "role": p.role,
                "territory": p.territory.name if p.territory_id else "",
                "quota": quota,
                "achievement": achievement,
                "attainment_pct": pct,
                "expected_commission": expected,
                "status": status_code,
                "status_label": status_label,
                "currency": normalize_currency(p.personal_currency),
                "plan_name": plan.plan_name if plan else "",
            }
        )
    quota_center.sort(key=lambda r: r["achievement"], reverse=True)

    avg_attainment = None
    pcts = [r["attainment_pct"] for r in quota_center if r["attainment_pct"] is not None]
    if pcts:
        avg_attainment = round(sum(pcts) / len(pcts), 1)

    territory_rows = []
    terr_agg = (
        orders.values("territory__name", "region")
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
            orders.filter(order_date__range=[range_start, range_end]).aggregate(
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
        s = _money(m_sales)
        c = _money(m_comm)
        rev_comm.append(
            {
                "period": cursor.strftime("%Y-%m"),
                "label": cursor.strftime("%b %Y"),
                "sales": s,
                "commission": c,
                "commission_pct": round((c / s) * 100, 2) if s > 0 else None,
            }
        )
        cursor = next_m

    pending_calcs = orders.filter(order_status="Booked").count()
    if hasattr(Order, "needs_recalculation"):
        pending_calcs = orders.filter(
            Q(needs_recalculation=True) | Q(order_status="Booked")
        ).count()

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
            "action_label": "Review",
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
        orders.order_by("-sales_amount").values(
            "order_id", "employee_id", "sales_amount", "order_date", "region"
        )[:8]
    )

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "business_group": effective_group or "all",
        "kpis": {
            "total_sales": sales_f,
            "commission_liability": curr,
            "commission_paid": _money(paid),
            "commission_pending": _money(pending),
            "quota_attainment": avg_attainment,
            "active_participants": active_participants,
            "avg_commission_rate": avg_rate,
            "leakage_risk": leakage_risk,
            "leakage_count": leakage_count,
            "liability_delta_pct": liability_delta_pct,
        },
        "plan_health": {
            "active_plans": active_plans,
            "blocked_plans": blocked,
            "missing_rules": missing_rules,
            "pending_approvals": pending_approvals,
        },
        "ops_alerts": ops_alerts,
        "quota_center": quota_center[:50],
        "territory_analytics": territory_rows,
        "revenue_vs_commission": rev_comm,
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
                    "order_date": d["order_date"].isoformat() if d["order_date"] else None,
                    "region": d.get("region") or "",
                }
                for d in largest_deals
            ],
        },
    }
