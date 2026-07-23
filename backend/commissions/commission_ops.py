"""
Commission Operations Center — aggregation, rollups, adjustments, bulk actions.

Does not change the commission calculation engine.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponse
from django.utils.dateparse import parse_date

from .audit import record_audit
from .currencies import normalize_currency
from .models import (
    AuditLog,
    Commission,
    CommissionAdjustment,
    UserProfile,
)
from .permissions import (
    user_can_view_finance_data,
    user_is_admin,
    user_is_finance,
    user_is_manager,
)
from .workflow import (
    approve_finance_commissions,
    approve_manager_commissions,
)


User = get_user_model()


def _money(value):
    try:
        return float(Decimal(str(value or 0)))
    except Exception:
        return 0.0


def _dec(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _status_label(status):
    mapping = {
        Commission.STATUS_CALCULATED: "Calculated",
        Commission.STATUS_MANAGER_APPROVED: "Under Review",
        Commission.STATUS_APPROVED: "Approved",
        Commission.STATUS_PAID: "Paid",
        Commission.STATUS_REJECTED: "Rejected",
        Commission.STATUS_FAILED: "Failed",
    }
    return mapping.get(status, status or "Unknown")


def _approval_stage(status):
    mapping = {
        Commission.STATUS_CALCULATED: "calculated",
        Commission.STATUS_MANAGER_APPROVED: "manager_review",
        Commission.STATUS_APPROVED: "finance_approved",
        Commission.STATUS_PAID: "paid",
        Commission.STATUS_REJECTED: "rejected",
        Commission.STATUS_FAILED: "failed",
    }
    return mapping.get(status, status or "unknown")


def _period_key(comm):
    order = getattr(getattr(comm, "sale", None), "order", None)
    if comm.period_start:
        start = comm.period_start
        end = comm.period_end or start
    elif order and order.order_date:
        start = date(order.order_date.year, order.order_date.month, 1)
        if order.order_date.month == 12:
            end = date(order.order_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            nxt = date(order.order_date.year, order.order_date.month + 1, 1)
            end = nxt - timedelta(days=1)
    else:
        calc = comm.calculated_at.date() if comm.calculated_at else date.today()
        start = date(calc.year, calc.month, 1)
        end = start
    return start.isoformat(), end.isoformat(), start, end


def _period_label(start, end):
    if not start:
        return "—"
    if start.month == end.month and start.year == end.year:
        return start.strftime("%B %Y")
    return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"


def scoped_commissions(request):
    from .enterprise_views import _commission_base_queryset, _commissions_for_user

    if user_can_view_finance_data(request) or user_is_manager(request):
        qs = _commission_base_queryset(request)
    else:
        qs = _commissions_for_user(request)
    org = getattr(request, "organization", None)
    if org:
        qs = qs.filter(Q(organization=org) | Q(sale__order__organization=org)).distinct()
    return qs.select_related(
        "employee",
        "sale",
        "sale__order",
        "sale__order__territory",
        "compensation_plan",
        "manager_approved_by",
        "approved_by",
        "reviewer",
        "payout_run",
    ).prefetch_related(
        Prefetch(
            "adjustments",
            queryset=CommissionAdjustment.objects.select_related("created_by").order_by(
                "-created_at"
            ),
        )
    )


def apply_ops_filters(queryset, request):
    from .enterprise_views import commission_date_q
    from .list_scope import commission_employee_search_q

    params = request.query_params if hasattr(request, "query_params") else request.GET
    start_date = parse_date(params.get("start_date") or "")
    end_date = parse_date(params.get("end_date") or "")
    if start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
    elif start_date:
        queryset = queryset.filter(commission_date_q(start_date, None))
    elif end_date:
        queryset = queryset.filter(commission_date_q(None, end_date))

    status_param = (params.get("status") or "").strip()
    valid = {c[0] for c in Commission.STATUS_CHOICES}
    if status_param in valid:
        queryset = queryset.filter(status=status_param)

    approval = (params.get("approval_status") or params.get("approval") or "").strip()
    approval_map = {
        "calculated": Commission.STATUS_CALCULATED,
        "under_review": Commission.STATUS_MANAGER_APPROVED,
        "manager_review": Commission.STATUS_MANAGER_APPROVED,
        "approved": Commission.STATUS_APPROVED,
        "finance_approved": Commission.STATUS_APPROVED,
        "payment_ready": Commission.STATUS_APPROVED,
        "paid": Commission.STATUS_PAID,
        "rejected": Commission.STATUS_REJECTED,
        "failed": Commission.STATUS_FAILED,
    }
    if approval in approval_map:
        queryset = queryset.filter(status=approval_map[approval])

    employee = (params.get("employee") or params.get("q") or "").strip()
    if employee:
        org = getattr(request, "organization", None)
        queryset = queryset.filter(
            commission_employee_search_q(employee, organization=org)
        )

    employee_id = (params.get("employee_id") or "").strip()
    if employee_id:
        queryset = queryset.filter(
            Q(sale__order__employee_id__icontains=employee_id)
            | Q(employee__email__icontains=employee_id)
        )

    plan = (params.get("plan") or params.get("compensation_plan") or "").strip()
    if plan:
        queryset = queryset.filter(
            Q(compensation_plan__plan_name__icontains=plan)
            | Q(compensation_plan__position_name__icontains=plan)
        )

    role = (params.get("role") or "").strip()
    department = (params.get("department") or "").strip()
    territory = (params.get("territory") or "").strip()
    if role or department:
        profile_q = Q()
        if role:
            profile_q &= Q(role__icontains=role)
        if department:
            profile_q &= Q(department__icontains=department)
        emails = list(
            UserProfile.objects.filter(profile_q).values_list("email", flat=True)[:2000]
        )
        if emails:
            queryset = queryset.filter(employee__email__in=emails)
        else:
            queryset = queryset.none()
    if territory:
        queryset = queryset.filter(
            Q(sale__order__territory__name__icontains=territory)
            | Q(sale__order__territory__code__icontains=territory)
            | Q(sale__order__region__icontains=territory)
        )

    calc_method = (
        params.get("calculation_method") or params.get("calculation_scope") or ""
    ).strip()
    if calc_method in {c[0] for c in Commission.SCOPE_CHOICES}:
        queryset = queryset.filter(calculation_scope=calc_method)

    try:
        min_amt = params.get("min_commission")
        if min_amt not in (None, ""):
            queryset = queryset.filter(commission_amount__gte=Decimal(str(min_amt)))
        max_amt = params.get("max_commission")
        if max_amt not in (None, ""):
            queryset = queryset.filter(commission_amount__lte=Decimal(str(max_amt)))
    except Exception:
        pass

    return queryset, start_date, end_date


def _profile_for_email(email, org=None):
    if not email:
        return None
    qs = UserProfile.objects.select_related("territory").filter(email__iexact=email)
    if org:
        profile = qs.filter(organization=org).first()
        if profile:
            return profile
        return qs.filter(organization__isnull=True).first()
    return qs.first()


def _adjustment_total(comm):
    total = Decimal("0")
    adjs = getattr(comm, "adjustments", None)
    if adjs is None:
        return total
    for adj in adjs.all():
        total += _dec(adj.amount)
    return total


def build_operations_summary(request):
    qs, start_date, end_date = apply_ops_filters(scoped_commissions(request), request)
    agg = qs.aggregate(liability=Sum("commission_amount"), count=Count("id"))
    by_status = {
        row["status"]: {"count": row["c"], "amount": _money(row["a"])}
        for row in qs.values("status").annotate(c=Count("id"), a=Sum("commission_amount"))
    }

    def bucket(status):
        return by_status.get(status) or {"count": 0, "amount": 0.0}

    calculated = bucket(Commission.STATUS_CALCULATED)
    under_review = bucket(Commission.STATUS_MANAGER_APPROVED)
    approved = bucket(Commission.STATUS_APPROVED)
    paid = bucket(Commission.STATUS_PAID)
    rejected = bucket(Commission.STATUS_REJECTED)
    failed = bucket(Commission.STATUS_FAILED)

    adj_qs = CommissionAdjustment.objects.filter(
        commission_id__in=qs.values_list("id", flat=True)
    )
    adj_agg = adj_qs.aggregate(total=Sum("amount"), count=Count("id"))
    exceptions = rejected["count"] + failed["count"]
    try:
        from .models import CommissionDispute

        exceptions += CommissionDispute.objects.filter(
            commission_id__in=qs.values_list("id", flat=True),
            status=CommissionDispute.STATUS_OPEN,
        ).count()
    except Exception:
        pass

    return {
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "kpis": {
            "commission_liability": _money(agg["liability"]),
            "calculated": calculated["amount"],
            "calculated_count": calculated["count"],
            "pending_approval": calculated["amount"] + under_review["amount"],
            "pending_approval_count": calculated["count"] + under_review["count"],
            "approved": approved["amount"],
            "approved_count": approved["count"],
            "paid": paid["amount"],
            "paid_count": paid["count"],
            "exceptions": exceptions,
            "adjustments": _money(adj_agg["total"]),
            "adjustments_count": adj_agg["count"] or 0,
            "record_count": agg["count"] or 0,
        },
        "pipeline": {
            "calculated": calculated["count"],
            "under_review": under_review["count"],
            "approved": approved["count"],
            "payment_ready": approved["count"],
            "paid": paid["count"],
            "rejected": rejected["count"],
            "failed": failed["count"],
        },
    }


def build_operations_grid(request):
    qs, start_date, end_date = apply_ops_filters(scoped_commissions(request), request)
    org = getattr(request, "organization", None)
    groups = defaultdict(
        lambda: {
            "commission_ids": [],
            "gross": Decimal("0"),
            "adjustments": Decimal("0"),
            "sales": Decimal("0"),
            "txn_count": 0,
            "statuses": set(),
            "plans": set(),
            "currencies": set(),
            "employee_name": "",
            "employee_email": "",
            "period_start": None,
            "period_end": None,
        }
    )

    for comm in qs.order_by("-calculated_at", "-id")[:5000]:
        p_start_s, p_end_s, p_start, p_end = _period_key(comm)
        email = (comm.employee.email or "").lower()
        key = (email, p_start_s, p_end_s)
        g = groups[key]
        g["commission_ids"].append(comm.id)
        g["gross"] += _dec(comm.commission_amount)
        g["adjustments"] += _adjustment_total(comm)
        order = getattr(getattr(comm, "sale", None), "order", None)
        sales = _dec(comm.source_sales_total)
        if sales <= 0 and order:
            sales = _dec(order.sales_amount)
        g["sales"] += sales
        g["txn_count"] += comm.source_order_count or 1
        g["statuses"].add(comm.status)
        if comm.compensation_plan_id:
            g["plans"].add(comm.compensation_plan.plan_name)
        cur = normalize_currency(
            comm.currency or (getattr(order, "currency", None) if order else None)
        )
        g["currencies"].add(cur)
        g["employee_name"] = comm.employee.name or g["employee_name"]
        g["employee_email"] = comm.employee.email or g["employee_email"]
        g["period_start"] = p_start
        g["period_end"] = p_end

    rows = []
    priority = [
        Commission.STATUS_FAILED,
        Commission.STATUS_REJECTED,
        Commission.STATUS_CALCULATED,
        Commission.STATUS_MANAGER_APPROVED,
        Commission.STATUS_APPROVED,
        Commission.STATUS_PAID,
    ]
    for (email, _ps, _pe), g in groups.items():
        profile = _profile_for_email(email, org)
        status = Commission.STATUS_CALCULATED
        for s in priority:
            if s in g["statuses"]:
                status = s
                break
        rows.append(
            {
                "row_key": f"{email}|{_ps}|{_pe}",
                "employee_name": (profile.name if profile and profile.name else None)
                or g["employee_name"]
                or email,
                "employee_email": g["employee_email"] or email,
                "employee_id": (profile.employee_id if profile else "")
                or email.split("@")[0],
                "role": (profile.role if profile else "") or "",
                "department": getattr(profile, "department", "") if profile else "",
                "territory": (
                    profile.territory.name if profile and profile.territory_id else ""
                ),
                "transaction_count": g["txn_count"],
                "sales_amount": _money(g["sales"]),
                "plan_name": ", ".join(sorted(g["plans"])) if g["plans"] else "—",
                "period_start": g["period_start"].isoformat()
                if g["period_start"]
                else None,
                "period_end": g["period_end"].isoformat() if g["period_end"] else None,
                "period_label": _period_label(g["period_start"], g["period_end"]),
                "gross_commission": _money(g["gross"]),
                "adjustments": _money(g["adjustments"]),
                "final_commission": _money(g["gross"] + g["adjustments"]),
                "status": status,
                "status_label": _status_label(status),
                "approval_stage": _approval_stage(status),
                "has_adjustments": g["adjustments"] != 0,
                "commission_ids": g["commission_ids"],
                "currency": next(iter(g["currencies"]), "INR"),
            }
        )

    rows.sort(key=lambda r: r["final_commission"], reverse=True)
    return {
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "count": len(rows),
        "results": rows,
    }


def _serialize_adjustment(adj):
    return {
        "id": adj.id,
        "adjustment_type": adj.adjustment_type,
        "amount": _money(adj.amount),
        "reason": adj.reason,
        "created_by": (
            adj.created_by.get_full_name() or adj.created_by.email
            if adj.created_by_id
            else None
        ),
        "created_at": adj.created_at.isoformat() if adj.created_at else None,
    }


def _serialize_line(comm):
    order = getattr(getattr(comm, "sale", None), "order", None)
    adj_total = _adjustment_total(comm)
    customer = "—"
    product = "—"
    if order:
        customer = (
            getattr(order, "customer_name", None)
            or getattr(order, "account_name", None)
            or "—"
        )
        product = (
            getattr(order, "product_name", None)
            or getattr(order, "product", None)
            or "—"
        )
    return {
        "id": comm.id,
        "order_id": order.order_id
        if order
        else (
            "Monthly summary"
            if comm.calculation_scope == Commission.SCOPE_EMPLOYEE_MONTH
            else None
        ),
        "customer": customer,
        "product": product,
        "amount": _money(order.sales_amount if order else comm.source_sales_total),
        "sales_credit": _money(
            comm.credit_amount
            if comm.credit_amount is not None
            else (order.sales_amount if order else comm.source_sales_total)
        ),
        "applied_rate": None,
        "commission_generated": _money(comm.commission_amount),
        "adjustments": _money(adj_total),
        "final_commission": _money(_dec(comm.commission_amount) + adj_total),
        "status": comm.status,
        "status_label": _status_label(comm.status),
        "plan_name": comm.compensation_plan.plan_name
        if comm.compensation_plan_id
        else None,
        "currency": normalize_currency(
            comm.currency or (getattr(order, "currency", None) if order else None)
        ),
        "order_date": order.order_date.isoformat()
        if order and order.order_date
        else None,
        "calculated_at": comm.calculated_at.isoformat() if comm.calculated_at else None,
        "rule_result_name": comm.rule_result_name or "",
        "calculation_scope": comm.calculation_scope,
    }


def build_operations_detail(request):
    from .commission_explanation import build_commission_explanation
    from .enterprise_views import commission_date_q

    params = request.query_params
    qs = scoped_commissions(request)
    commission_id = params.get("commission_id")
    employee_id = (params.get("employee_id") or "").strip()
    email = (params.get("employee_email") or "").strip()
    period_start = parse_date(params.get("period_start") or "")
    period_end = parse_date(params.get("period_end") or "")
    ids_param = params.get("commission_ids") or ""

    if commission_id:
        qs = qs.filter(id=commission_id)
    elif ids_param:
        try:
            id_list = [int(x) for x in ids_param.split(",") if x.strip()]
        except ValueError:
            id_list = []
        qs = qs.filter(id__in=id_list)
    else:
        if employee_id:
            qs = qs.filter(
                Q(sale__order__employee_id__iexact=employee_id)
                | Q(employee__email__icontains=employee_id)
            )
        if email:
            qs = qs.filter(employee__email__iexact=email)
        if period_start and period_end:
            qs = qs.filter(commission_date_q(period_start, period_end))

    commissions = list(qs.order_by("calculated_at", "id")[:500])
    if not commissions:
        return None

    primary = commissions[0]
    org = getattr(request, "organization", None)
    profile = _profile_for_email(primary.employee.email, org)
    _ps, _pe, p_start, p_end = _period_key(primary)
    if period_start:
        p_start = period_start
    if period_end:
        p_end = period_end

    gross = sum((_dec(c.commission_amount) for c in commissions), Decimal("0"))
    adj_total = sum((_adjustment_total(c) for c in commissions), Decimal("0"))
    sales = Decimal("0")
    for c in commissions:
        line_sales = _dec(c.source_sales_total)
        if line_sales <= 0:
            order = getattr(getattr(c, "sale", None), "order", None)
            line_sales = _dec(getattr(order, "sales_amount", 0) if order else 0)
        sales += line_sales

    adjustments = []
    for c in commissions:
        for adj in c.adjustments.all():
            adjustments.append(_serialize_adjustment(adj))

    explanations = []
    for c in commissions[:10]:
        try:
            explanations.append(
                {"commission_id": c.id, "explanation": build_commission_explanation(c)}
            )
        except Exception as exc:
            explanations.append(
                {"commission_id": c.id, "explanation": None, "error": str(exc)}
            )

    approvals = []
    for c in commissions:
        if c.calculated_at:
            approvals.append(
                {
                    "stage": "Calculated",
                    "status": "done",
                    "approver": "System",
                    "date": c.calculated_at.isoformat(),
                    "comments": "",
                    "commission_id": c.id,
                }
            )
        if c.manager_approved_at:
            approvals.append(
                {
                    "stage": "Manager Review",
                    "status": "done",
                    "approver": (
                        c.manager_approved_by.get_full_name()
                        or c.manager_approved_by.email
                        if c.manager_approved_by_id
                        else None
                    ),
                    "date": c.manager_approved_at.isoformat(),
                    "comments": "",
                    "commission_id": c.id,
                }
            )
        if c.approved_at:
            approvals.append(
                {
                    "stage": "Finance Approval",
                    "status": "done",
                    "approver": (
                        c.approved_by.get_full_name() or c.approved_by.email
                        if c.approved_by_id
                        else None
                    ),
                    "date": c.approved_at.isoformat(),
                    "comments": "",
                    "commission_id": c.id,
                }
            )
        if c.paid_at:
            approvals.append(
                {
                    "stage": "Paid",
                    "status": "done",
                    "approver": None,
                    "date": c.paid_at.isoformat(),
                    "comments": "",
                    "commission_id": c.id,
                }
            )
        if c.status == Commission.STATUS_REJECTED:
            approvals.append(
                {
                    "stage": "Rejected",
                    "status": "rejected",
                    "approver": None,
                    "date": None,
                    "comments": c.rejection_reason or "",
                    "commission_id": c.id,
                }
            )

    comm_ids = [c.id for c in commissions]
    email_l = (primary.employee.email or "").lower()
    audit = []
    for log in AuditLog.objects.filter(organization=org).filter(
        action__startswith="commission"
    ).order_by("-created_at")[:120]:
        detail = log.detail or {}
        related = detail.get("commission_id") in comm_ids
        ids = detail.get("commission_ids") or []
        if any(i in comm_ids for i in ids):
            related = True
        if (detail.get("employee_email") or "").lower() == email_l:
            related = True
        if not related:
            continue
        audit.append(
            {
                "id": log.id,
                "action": log.action,
                "user_email": log.user_email,
                "detail": detail,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )

    statuses = {c.status for c in commissions}
    status = Commission.STATUS_CALCULATED
    for s in [
        Commission.STATUS_FAILED,
        Commission.STATUS_REJECTED,
        Commission.STATUS_CALCULATED,
        Commission.STATUS_MANAGER_APPROVED,
        Commission.STATUS_APPROVED,
        Commission.STATUS_PAID,
    ]:
        if s in statuses:
            status = s
            break

    return {
        "overview": {
            "employee_name": (profile.name if profile and profile.name else None)
            or primary.employee.name,
            "employee_email": primary.employee.email,
            "employee_id": (profile.employee_id if profile else "")
            or primary.employee.email.split("@")[0],
            "role": (profile.role if profile else "") or "",
            "territory": (
                profile.territory.name if profile and profile.territory_id else ""
            ),
            "period_start": p_start.isoformat() if p_start else None,
            "period_end": p_end.isoformat() if p_end else None,
            "period_label": _period_label(p_start, p_end),
            "plan_name": primary.compensation_plan.plan_name
            if primary.compensation_plan_id
            else "—",
            "sales_amount": _money(sales),
            "gross_commission": _money(gross),
            "adjustments": _money(adj_total),
            "final_commission": _money(gross + adj_total),
            "status": status,
            "status_label": _status_label(status),
            "approval_stage": _approval_stage(status),
            "has_adjustments": adj_total != 0,
            "commission_ids": comm_ids,
            "currency": normalize_currency(primary.currency),
            "reviewer": (
                primary.reviewer.get_full_name() or primary.reviewer.email
                if primary.reviewer_id
                else None
            ),
            "transaction_count": len(commissions),
        },
        "lines": [_serialize_line(c) for c in commissions],
        "explanations": explanations,
        "adjustments": adjustments,
        "approvals": approvals,
        "audit": audit,
    }


def create_adjustment(request, data):
    commission_id = data.get("commission_id")
    if not commission_id:
        return None, {"error": "commission_id is required"}
    if not user_can_view_finance_data(request):
        return None, {"error": "Only finance or admin can create adjustments"}
    qs = scoped_commissions(request).filter(id=commission_id)
    comm = qs.first()
    if not comm:
        return None, {"error": "Commission not found"}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return None, {"error": "reason is required"}
    adj_type = (data.get("adjustment_type") or CommissionAdjustment.TYPE_MANUAL).strip()
    valid_types = {c[0] for c in CommissionAdjustment.TYPE_CHOICES}
    if adj_type not in valid_types:
        return None, {"error": f"adjustment_type must be one of {sorted(valid_types)}"}
    try:
        amount = Decimal(str(data.get("amount")))
    except Exception:
        return None, {"error": "amount must be a number"}
    if adj_type == CommissionAdjustment.TYPE_CLAWBACK and amount > 0:
        amount = -abs(amount)

    adj = CommissionAdjustment.objects.create(
        organization=comm.organization or getattr(request, "organization", None),
        commission=comm,
        adjustment_type=adj_type,
        amount=amount,
        reason=reason,
        created_by=request.user,
    )
    record_audit(
        request,
        "commission_adjusted",
        {
            "commission_id": comm.id,
            "adjustment_id": adj.id,
            "amount": str(amount),
            "adjustment_type": adj_type,
            "reason": reason,
            "employee_email": comm.employee.email,
        },
    )
    return adj, None


def run_bulk_action(request, data):
    action = (data.get("action") or "").strip()
    ids = data.get("commission_ids") or data.get("ids") or []
    if not isinstance(ids, list):
        return None, {"error": "commission_ids must be a list"}
    ids = [int(i) for i in ids if str(i).isdigit() or isinstance(i, int)]
    if not ids:
        return None, {"error": "commission_ids required"}

    qs = scoped_commissions(request).filter(id__in=ids)
    comment = (data.get("comment") or data.get("reason") or "").strip()

    if action in ("approve_manager", "manager_approve"):
        if not (user_is_manager(request) or user_is_admin(request)):
            return None, {"error": "Only managers or admins can manager-approve"}
        count = approve_manager_commissions(qs, request.user)
        record_audit(
            request,
            "commission_bulk_manager_approved",
            {"approved": count, "commission_ids": ids, "comment": comment},
        )
        return {"action": action, "updated": count}, None

    if action in ("approve_finance", "finance_approve", "approve"):
        if not (user_is_finance(request) or user_is_admin(request)):
            return None, {"error": "Only finance or admins can finance-approve"}
        count = approve_finance_commissions(qs, request.user)
        record_audit(
            request,
            "commission_bulk_finance_approved",
            {"approved": count, "commission_ids": ids, "comment": comment},
        )
        return {"action": action, "updated": count}, None

    if action == "reject":
        if not user_can_view_finance_data(request):
            return None, {"error": "Only finance or admin can reject"}
        if not comment:
            return None, {"error": "reason/comment required to reject"}
        count = qs.exclude(status=Commission.STATUS_PAID).update(
            status=Commission.STATUS_REJECTED,
            rejection_reason=comment,
        )
        record_audit(
            request,
            "commission_rejected",
            {"updated": count, "commission_ids": ids, "reason": comment},
        )
        return {"action": action, "updated": count}, None

    if action == "assign_reviewer":
        if not (user_can_view_finance_data(request) or user_is_manager(request)):
            return None, {"error": "Insufficient permission to assign reviewer"}
        reviewer_id = data.get("reviewer_id")
        reviewer_email = (data.get("reviewer_email") or "").strip()
        reviewer = None
        if reviewer_id:
            reviewer = User.objects.filter(id=reviewer_id).first()
        elif reviewer_email:
            reviewer = User.objects.filter(email__iexact=reviewer_email).first()
        if not reviewer:
            return None, {"error": "reviewer_id or reviewer_email required"}
        count = qs.update(reviewer=reviewer)
        record_audit(
            request,
            "commission_bulk_assign_reviewer",
            {
                "updated": count,
                "commission_ids": ids,
                "reviewer_email": reviewer.email,
            },
        )
        return {"action": action, "updated": count, "reviewer": reviewer.email}, None

    if action == "recalculate":
        if not user_is_admin(request):
            return None, {"error": "Only admins can recalculate"}
        from .services import calculate_commission_for_order

        processed = 0
        failed = 0
        skipped = 0
        for comm in qs.select_related("sale__order"):
            order = getattr(getattr(comm, "sale", None), "order", None)
            if not order:
                failed += 1
                continue
            if comm.status in Commission.LOCKED_STATUSES and not data.get("force"):
                skipped += 1
                continue
            try:
                calculate_commission_for_order(order, force=bool(data.get("force")))
                processed += 1
            except Exception:
                failed += 1
        record_audit(
            request,
            "commission_bulk_recalculated",
            {
                "processed": processed,
                "failed": failed,
                "skipped": skipped,
                "commission_ids": ids,
            },
        )
        return {
            "action": action,
            "processed": processed,
            "failed": failed,
            "skipped": skipped,
        }, None

    return None, {"error": f"Unknown action: {action}"}


def build_operations_export(request):
    report = (request.query_params.get("report") or "payroll").strip().lower()
    fmt = (request.query_params.get("format") or "csv").strip().lower()
    qs, start_date, end_date = apply_ops_filters(scoped_commissions(request), request)

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if report == "audit":
        writer.writerow(["Timestamp", "Action", "User", "Detail"])
        org = getattr(request, "organization", None)
        logs = (
            AuditLog.objects.filter(organization=org)
            .filter(action__startswith="commission")
            .order_by("-created_at")[:2000]
        )
        for log in logs:
            writer.writerow(
                [
                    log.created_at.isoformat() if log.created_at else "",
                    log.action,
                    log.user_email,
                    str(log.detail or {}),
                ]
            )
        filename = "commission-audit-report.csv"
    elif report in ("finance", "finance_report"):
        writer.writerow(
            [
                "Employee",
                "Email",
                "Employee ID",
                "Order / Period",
                "Plan",
                "Gross Commission",
                "Adjustments",
                "Final Commission",
                "Status",
                "Currency",
            ]
        )
        org = getattr(request, "organization", None)
        for comm in qs.order_by("employee__name", "id")[:5000]:
            order = getattr(getattr(comm, "sale", None), "order", None)
            profile = _profile_for_email(comm.employee.email, org)
            adj = _adjustment_total(comm)
            writer.writerow(
                [
                    comm.employee.name,
                    comm.employee.email,
                    (profile.employee_id if profile else ""),
                    order.order_id if order else (comm.period_start or ""),
                    comm.compensation_plan.plan_name
                    if comm.compensation_plan_id
                    else "",
                    str(comm.commission_amount),
                    str(adj),
                    str(_dec(comm.commission_amount) + adj),
                    comm.status,
                    normalize_currency(comm.currency),
                ]
            )
        filename = "commission-finance-report.csv"
    elif report in ("statements", "employee_statements"):
        grid = build_operations_grid(request)
        writer.writerow(
            [
                "Employee",
                "Employee ID",
                "Period",
                "Sales",
                "Gross Commission",
                "Adjustments",
                "Final Commission",
                "Status",
                "Currency",
            ]
        )
        for row in grid["results"]:
            writer.writerow(
                [
                    row["employee_name"],
                    row["employee_id"],
                    row["period_label"],
                    row["sales_amount"],
                    row["gross_commission"],
                    row["adjustments"],
                    row["final_commission"],
                    row["status_label"],
                    row["currency"],
                ]
            )
        filename = "employee-commission-statements.csv"
    else:
        writer.writerow(
            [
                "Employee Name",
                "Employee Email",
                "Employee ID",
                "Commission Amount",
                "Adjustments",
                "Final Amount",
                "Status",
                "Currency",
                "Period Start",
                "Period End",
            ]
        )
        org = getattr(request, "organization", None)
        payroll_qs = qs.filter(status=Commission.STATUS_APPROVED)
        if not payroll_qs.exists():
            payroll_qs = qs
        for comm in payroll_qs.order_by("employee__email")[:5000]:
            profile = _profile_for_email(comm.employee.email, org)
            adj = _adjustment_total(comm)
            _a, _b, start, end = _period_key(comm)
            writer.writerow(
                [
                    comm.employee.name,
                    comm.employee.email,
                    (profile.employee_id if profile else ""),
                    str(comm.commission_amount),
                    str(adj),
                    str(_dec(comm.commission_amount) + adj),
                    comm.status,
                    normalize_currency(comm.currency),
                    start.isoformat() if start else "",
                    end.isoformat() if end else "",
                ]
            )
        filename = "payroll-commissions.csv"

    if fmt == "xlsx":
        filename = filename.replace(".csv", ".xlsx.csv")
    elif fmt == "pdf":
        html = (
            "<html><head><title>Commission Export</title>"
            "<style>body{font-family:Segoe UI,Arial,sans-serif;font-size:12px}"
            "pre{white-space:pre-wrap}</style></head><body>"
            "<h1>Commission Export</h1><pre>"
            + buffer.getvalue().replace("<", "&lt;")
            + "</pre></body></html>"
        )
        response = HttpResponse(html, content_type="text/html")
        response["Content-Disposition"] = (
            f'attachment; filename="{filename.replace(".csv", ".html")}"'
        )
        record_audit(
            request,
            "commission_exported",
            {"report": report, "format": "pdf_html"},
        )
        return response

    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    record_audit(
        request,
        "commission_exported",
        {
            "report": report,
            "format": fmt,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    )
    return response
