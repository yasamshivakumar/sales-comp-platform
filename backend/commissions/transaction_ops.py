"""
Sales Transaction Operations enrichment — additive fields on Order.

Does not change commission eligibility (still order_status ≈ Success).
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone


# Lifecycle display mapping — engine still keys off Success for payouts.
LIFECYCLE = {
    "imported": "Imported",
    "booked": "Pending Review",
    "pending": "Pending Review",
    "pending review": "Pending Review",
    "approved": "Approved",
    "success": "Approved",
    "commission calculated": "Commission Calculated",
    "paid": "Paid",
    "rejected": "Rejected",
    "cancelled": "Cancelled",
    "failed": "Failed",
}


def normalize_status(value):
    return str(value or "").strip().lower()


def lifecycle_label(order_status, has_commission=False, commission_paid=False):
    key = normalize_status(order_status)
    if commission_paid or key == "paid":
        return "Paid"
    if has_commission and key in ("success", "approved", "commission calculated"):
        return "Commission Calculated"
    return LIFECYCLE.get(key, order_status or "Pending Review")


def commission_status_for_order(order, commission=None):
    """Derived commission readiness / outcome for UI."""
    status = normalize_status(order.order_status)
    if status in ("cancelled", "rejected"):
        return "cancelled"
    if status == "failed":
        return "failed"
    if not order.employee_id:
        return "blocked"
    if commission is not None:
        cstatus = normalize_status(getattr(commission, "status", ""))
        if cstatus == "paid":
            return "paid"
        return "calculated"
    if status in ("success", "approved"):
        return "failed"  # approved but no commission row yet
    return "pending"


def resolve_primary_commission(order):
    """
    Resolve the commission row that backs this transaction in the UI.
    Matches OrderSerializer / monthly aggregate attribution:
    sale-linked commission first, then employee-month commission.
    """
    from .models import Commission

    sale = getattr(order, "sale_record", None)
    if sale:
        prefetched = getattr(sale, "_prefetched_objects_cache", {})
        if "commission_set" in prefetched:
            commissions = prefetched["commission_set"]
            if commissions:
                return commissions[0]
        commission = sale.commission_set.order_by("id").first()
        if commission:
            return commission

    order_commission = (
        Commission.objects.filter(
            sale__order=order,
            organization=getattr(order, "organization", None),
        )
        .order_by("id")
        .first()
    )
    if order_commission:
        return order_commission

    if not getattr(order, "employee_id", None) or not getattr(order, "order_date", None):
        return None

    from .currencies import normalize_currency
    from .plan_periods import month_bounds
    from .services import _profile_for_employee

    period_start, _period_end = month_bounds(order.order_date.year, order.order_date.month)
    profile = _profile_for_employee(
        order.employee_id,
        getattr(order, "organization", None),
    )
    emails = [f"{order.employee_id}@company.com"]
    if profile and profile.email:
        emails.append(profile.email)
    return (
        Commission.objects.filter(
            calculation_scope=Commission.SCOPE_EMPLOYEE_MONTH,
            organization=getattr(order, "organization", None),
            period_start=period_start,
            currency__iexact=normalize_currency(getattr(order, "currency", None)),
            employee__email__in=emails,
        )
        .order_by("id")
        .first()
    )


def default_sales_credits(order):
    stored = getattr(order, "sales_credits", None) or []
    if stored:
        return stored
    if not order.employee_id:
        return []
    return [
        {
            "employee_id": order.employee_id,
            "name": order.employee_id,
            "role": "Primary Sales Rep",
            "percent": 100,
        }
    ]


def enrich_order_transaction_fields(order, commission=None):
    """Additive payload merged into OrderSerializer representation."""
    has_comm = commission is not None
    paid = has_comm and normalize_status(getattr(commission, "status", "")) == "paid"
    plan_name = None
    plan_id = None
    if commission is not None and getattr(commission, "compensation_plan_id", None):
        plan = getattr(commission, "compensation_plan", None)
        plan_name = getattr(plan, "plan_name", None) if plan else None
        plan_id = commission.compensation_plan_id

    territory_name = None
    if getattr(order, "territory_id", None):
        territory = getattr(order, "territory", None)
        territory_name = getattr(territory, "name", None) or str(order.territory_id)

    return {
        "transaction_id": order.order_id,
        "customer": getattr(order, "customer_name", None) or order.customer_segment or "",
        "product": order.product_name or order.service_name or "",
        "sales_rep": order.employee_id or "",
        "lifecycle_status": lifecycle_label(order.order_status, has_comm, paid),
        "commission_status": commission_status_for_order(order, commission),
        "commission_plan_name": plan_name,
        "commission_plan_id": plan_id,
        "sales_credits": default_sales_credits(order),
        "source": getattr(order, "source", None)
        or (order.crm_provider and "crm")
        or "manual",
        "territory_name": territory_name,
        "is_locked": normalize_status(order.order_status) in ("success", "approved", "paid"),
    }


def build_order_commission_breakdown(order, commission=None):
    """Transparent calculation summary for Transaction workspace."""
    if commission is None:
        return {
            "available": False,
            "reason": "Commission not calculated yet. Approve (Success) to run calculation.",
            "steps": [],
            "total": None,
            "plan_name": None,
            "rule": None,
        }

    try:
        from .commission_explanation import build_commission_explanation

        explanation = build_commission_explanation(commission)
    except Exception:
        explanation = None

    if explanation and not explanation.get("error"):
        return {
            "available": True,
            "plan_name": explanation.get("plan_name")
            or getattr(getattr(commission, "compensation_plan", None), "plan_name", None),
            "rule": explanation.get("table_type") or explanation.get("rule_summary"),
            "steps": explanation.get("lines") or explanation.get("breakdown") or [],
            "total": float(commission.commission_amount or 0),
            "currency": commission.currency,
            "explanation": explanation,
            "note": (
                "Monthly aggregate commission for this sales rep period "
                "may include multiple successful orders."
                if getattr(commission, "calculation_scope", "") == "employee_month"
                else None
            ),
        }

    return {
        "available": True,
        "plan_name": getattr(getattr(commission, "compensation_plan", None), "plan_name", None),
        "rule": None,
        "steps": [],
        "total": float(commission.commission_amount or 0),
        "currency": commission.currency,
        "explanation": explanation,
    }


def build_order_history(order, limit=30):
    """Audit trail entries related to this order."""
    from .models import AuditLog

    org = getattr(order, "organization", None)
    qs = AuditLog.objects.select_related("user").order_by("-created_at")
    if org is not None:
        qs = qs.filter(organization=org)
    rows = []
    oid = str(order.order_id)
    for log in qs[:200]:
        # Model field is `detail` (JSON), not `details`
        raw = getattr(log, "detail", None)
        details = raw if isinstance(raw, dict) else {}
        if str(details.get("order_id") or "") != oid and str(details.get("transaction_id") or "") != oid:
            ids = details.get("order_ids") or details.get("transaction_ids") or []
            if oid not in [str(x) for x in ids]:
                continue
        rows.append(
            {
                "id": log.id,
                "action": log.action,
                "user": (
                    getattr(log.user, "email", None)
                    or getattr(log, "user_email", None)
                    or "System"
                ),
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "details": details,
            }
        )
        if len(rows) >= limit:
            break

    # Seed synthetic timeline from timestamps when audit sparse
    if not any(r["action"] in ("order_created", "Created") for r in rows) and order.uploaded_at:
        rows.append(
            {
                "id": f"created-{order.id}",
                "action": "Created",
                "user": "System",
                "timestamp": order.uploaded_at.isoformat(),
                "details": {},
            }
        )
    return rows


def build_orders_summary(organization, queryset):
    """KPI + action center for Sales Transaction Center."""
    qs = queryset
    total = qs.count()
    booked = qs.filter(order_status__iexact="Booked").count()
    pending = qs.filter(
        Q(order_status__iexact="Booked")
        | Q(order_status__iexact="Pending")
        | Q(order_status__iexact="Imported")
    ).count()
    success = qs.filter(order_status__iexact="Success").count()
    failed = qs.filter(
        Q(order_status__iexact="Failed") | Q(order_status__iexact="Rejected")
    ).count()
    cancelled = qs.filter(order_status__iexact="Cancelled").count()

    sales_agg = qs.aggregate(total=Sum("sales_amount"))
    total_sales = float(sales_agg["total"] or 0)

    missing_rep = qs.filter(Q(employee_id__isnull=True) | Q(employee_id="")).count()

    # Duplicate transaction ids within org
    dup_ids = (
        qs.values("order_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .count()
    )

    # Commission generated from related commissions (org-scoped)
    from .models import Commission

    comm_qs = Commission.objects.all()
    if organization is not None:
        comm_qs = comm_qs.filter(organization=organization)
    commission_generated = float(
        comm_qs.aggregate(total=Sum("commission_amount"))["total"] or 0
    )

    # Align with grid: employee-month commissions count as calculated
    success_orders = list(
        qs.filter(order_status__iexact="Success")
        .select_related("sale_record")
        .prefetch_related("sale_record__commission_set")[:500]
    )
    calc_failed = 0
    calculated = 0
    for order in success_orders:
        if resolve_primary_commission(order) is not None:
            calculated += 1
        else:
            calc_failed += 1

    action_center = []
    if pending:
        action_center.append(
            {
                "code": "pending_approval",
                "title": "Orders Pending Approval",
                "subtitle": f"{pending} orders require review",
                "impact": "Commission cannot run until approved",
                "count": pending,
                "cta": "Review",
                "filter": {"order_status": "Booked"},
            }
        )
    if dup_ids:
        action_center.append(
            {
                "code": "duplicates",
                "title": "Duplicate Orders Detected",
                "subtitle": f"{dup_ids} possible duplicates",
                "impact": "Risk of double payout",
                "count": dup_ids,
                "cta": "Review",
                "filter": {"q": ""},
            }
        )
    if missing_rep:
        action_center.append(
            {
                "code": "missing_rep",
                "title": "Missing Sales Rep Assignment",
                "subtitle": f"{missing_rep} orders cannot calculate commission",
                "impact": "Employees cannot receive credit",
                "count": missing_rep,
                "cta": "Review",
                "filter": {"missing_rep": "1"},
            }
        )
    if calc_failed:
        action_center.append(
            {
                "code": "calc_failed",
                "title": "Failed Commission Calculation",
                "subtitle": f"{calc_failed} orders require attention",
                "impact": "Approved but no commission produced",
                "count": calc_failed,
                "cta": "Review",
                "filter": {"order_status": "Success", "commission_status": "failed"},
            }
        )

    return {
        "total_transactions": total,
        "pending_review": pending,
        "approved_transactions": success,
        "commission_calculated": calculated,
        "failed_transactions": failed,
        "cancelled_transactions": cancelled,
        "total_sales_value": round(total_sales, 2),
        "commission_generated": round(commission_generated, 2),
        "booked_transactions": booked,
        "missing_sales_rep": missing_rep,
        "duplicate_groups": dup_ids,
        "action_center": action_center,
        "as_of": timezone.now().isoformat(),
    }


def validate_order_csv_rows(rows, organization, existing_order_ids=None):
    """
    Dry-run validation for enterprise import wizard.
    Returns preview rows + errors without writing.
    """
    existing = existing_order_ids or set()
    if organization is not None and not existing_order_ids:
        from .models import Order

        existing = set(
            Order.objects.filter(organization=organization).values_list("order_id", flat=True)
        )

    errors = []
    preview = []
    seen = set()
    for idx, row in enumerate(rows, start=2):  # header = 1
        order_id = str(row.get("order_id") or row.get("Order ID") or "").strip()
        amount_raw = row.get("sales_amount") or row.get("Sales Amount") or row.get("amount")
        employee = str(row.get("employee_id") or row.get("Employee ID") or "").strip()
        row_errors = []
        if not order_id:
            row_errors.append("Missing Order ID")
        elif order_id in existing:
            row_errors.append("Duplicate Order ID (already exists)")
        elif order_id in seen:
            row_errors.append("Duplicate Order ID (in file)")
        try:
            amount = Decimal(str(amount_raw or "0").replace(",", ""))
            if amount < 0:
                row_errors.append("Invalid Amount (negative)")
        except Exception:
            row_errors.append("Invalid Amount")
            amount = None
        if not employee:
            row_errors.append("Missing Employee")

        if row_errors:
            errors.append({"row": idx, "order_id": order_id or "—", "errors": row_errors})
        else:
            seen.add(order_id)
            preview.append(
                {
                    "row": idx,
                    "order_id": order_id,
                    "employee_id": employee,
                    "sales_amount": float(amount) if amount is not None else 0,
                    "product_name": row.get("product_name") or row.get("Product") or "",
                    "customer_name": row.get("customer_name") or row.get("Customer") or "",
                    "order_status": row.get("order_status") or "Booked",
                }
            )

    return {
        "valid": len(errors) == 0,
        "preview_count": len(preview),
        "error_count": len(errors),
        "preview": preview[:50],
        "errors": errors[:100],
    }
