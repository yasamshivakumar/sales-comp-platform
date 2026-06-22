"""Enterprise features: statements, workflow, disputes, payouts, territories, leaderboard."""

import csv
import io
from decimal import Decimal

from django.db.models import Case, CharField, Count, Q, Sum, When
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import record_audit
from .currencies import normalize_currency
from .emails import (
    notify_commission_dispute,
    notify_commission_finance_approved,
    notify_commission_manager_approved,
    notify_commission_paid,
)
from .models import (
    Commission,
    CommissionDispute,
    Order,
    PayoutRun,
    Territory,
    UserProfile,
)
from .tenants import filter_queryset_by_organization
from .user_scope import profile_commission_q
from .permissions import (
    get_request_user_profile,
    require_admin,
    require_finance_or_admin,
    user_can_view_finance_data,
    user_is_admin,
    user_is_finance,
    user_is_manager,
)
from .serializers import (
    CommissionDisputeSerializer,
    PayoutRunSerializer,
    TerritorySerializer,
)
from .workflow import (
    approve_finance_commissions,
    approve_manager_commissions,
    commission_has_open_dispute,
    mark_payout_run_paid,
)


def commission_date_q(start_date=None, end_date=None):
    if start_date and end_date:
        return Q(sale__order__order_date__range=[start_date, end_date]) | Q(
            period_start__lte=end_date,
            period_end__gte=start_date,
        )
    if start_date:
        return Q(sale__order__order_date__gte=start_date) | Q(period_end__gte=start_date)
    if end_date:
        return Q(sale__order__order_date__lte=end_date) | Q(period_start__lte=end_date)
    return Q()


def with_commission_currency(queryset):
    return queryset.annotate(
        report_currency=Case(
            When(currency="", then="sale__order__currency"),
            default="currency",
            output_field=CharField(),
        )
    )


def _commission_base_queryset(request):
    queryset = Commission.objects.select_related(
        "employee",
        "sale",
        "sale__order",
        "compensation_plan",
        "manager_approved_by",
        "approved_by",
        "payout_run",
    )
    return filter_queryset_by_organization(
        queryset,
        getattr(request, "organization", None),
    )


def _commissions_for_user(request):
    queryset = _commission_base_queryset(request)
    if user_can_view_finance_data(request) or user_is_manager(request):
        return queryset

    profile = get_request_user_profile(request)
    if not profile:
        return queryset.none()

    return queryset.filter(profile_commission_q(profile, request.user.email))


def _apply_commission_filters(queryset, request):
    from .business_groups import apply_business_group_to_commissions, resolve_dashboard_business_group
    from .permissions import user_is_admin, user_is_finance

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    if start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
    status_param = request.query_params.get("status")
    valid_statuses = {c[0] for c in Commission.STATUS_CHOICES}
    if status_param in valid_statuses:
        queryset = queryset.filter(status=status_param)
    territory_id = request.query_params.get("territory_id")
    if territory_id:
        queryset = queryset.filter(
            Q(sale__order__territory_id=territory_id)
            | Q(sale__order__territory__isnull=True)
        )
    profile = get_request_user_profile(request)
    can_view_all_groups = user_is_admin(request) or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, profile, can_view_all_groups
    )
    queryset = apply_business_group_to_commissions(
        queryset,
        effective_group,
        organization=getattr(request, "organization", None),
    )
    return queryset, start_date, end_date


def _parse_approval_body(request):
    ids = request.data.get("ids") or []
    start_date = parse_date(request.data.get("start_date") or "")
    end_date = parse_date(request.data.get("end_date") or "")
    queryset = _commission_base_queryset(request)
    org = getattr(request, "organization", None)
    if org:
        queryset = queryset.filter(organization=org)
    if ids:
        queryset = queryset.filter(id__in=ids)
    elif start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
    else:
        return None, None, None, Response(
            {"error": "Provide commission ids and/or start_date + end_date"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return queryset, start_date, end_date, None


def _commission_rate_pct(amount, sales_amount):
    if not sales_amount or sales_amount <= 0:
        return None
    return round(float(amount / sales_amount * 100), 2)


def _statement_line_from_commission(comm, profile):
    order = comm.sale.order if comm.sale_id and comm.sale.order_id else None
    amount = comm.commission_amount or Decimal("0.00")
    is_monthly_summary = (
        getattr(comm, "calculation_scope", "") == Commission.SCOPE_EMPLOYEE_MONTH
    )
    sales = (
        comm.source_sales_total
        if is_monthly_summary and comm.source_sales_total is not None
        else (order.sales_amount if order else None)
    )
    currency = normalize_currency(
        getattr(comm, "currency", None)
        or getattr(order, "currency", None)
        or (profile.personal_currency if profile else None)
    )
    profile_employee_id = profile.employee_id if profile else None
    profile_email = profile.email if profile else None
    is_manager_credit = bool(
        order
        and profile_employee_id
        and order.employee_id
        and order.employee_id != profile_employee_id
        and profile_email
        and comm.employee.email == profile_email
    )
    return {
        "id": comm.id,
        "order_id": (
            order.order_id
            if order
            else ("Monthly summary" if is_monthly_summary else None)
        ),
        "order_date": (
            str(order.order_date)
            if order
            else (str(comm.period_start) if comm.period_start else None)
        ),
        "product": (
            (order.product_name or order.service_name)
            if order
            else (
                f"{comm.source_order_count} order monthly total"
                if is_monthly_summary
                else None
            )
        ),
        "sales_amount": str(sales) if sales is not None else None,
        "commission_amount": str(amount),
        "currency": currency,
        "commission_rate": _commission_rate_pct(amount, sales),
        "status": comm.status,
        "plan_name": (
            comm.compensation_plan.plan_name if comm.compensation_plan_id else None
        ),
        "employee_name": comm.employee.name,
        "employee_email": comm.employee.email,
        "calculated_at": comm.calculated_at.isoformat() if comm.calculated_at else None,
        "manager_approved_at": (
            comm.manager_approved_at.isoformat() if comm.manager_approved_at else None
        ),
        "approved_at": comm.approved_at.isoformat() if comm.approved_at else None,
        "paid_at": comm.paid_at.isoformat() if comm.paid_at else None,
        "payout_run_id": comm.payout_run_id,
        "line_type": "credit" if is_manager_credit else "order",
        "credit_reason": (
            "Manager override / hierarchy split" if is_manager_credit else None
        ),
        "has_open_dispute": commission_has_open_dispute(comm),
        "calculation_scope": comm.calculation_scope,
        "period_start": str(comm.period_start) if comm.period_start else None,
        "period_end": str(comm.period_end) if comm.period_end else None,
        "source_order_count": comm.source_order_count,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_statement(request):
    """Commission statement for the logged-in employee (or all for finance/admin)."""
    queryset = _commissions_for_user(request)
    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = queryset.select_related(
        "employee",
        "sale",
        "sale__order",
        "compensation_plan",
        "payout_run",
    )

    profile = get_request_user_profile(request)
    profile_employee_id = profile.employee_id if profile else None

    if profile_employee_id:
        employee_orders = Order.objects.filter(employee_id=profile_employee_id)
        if start_date and end_date:
            employee_orders = employee_orders.filter(order_date__range=[start_date, end_date])
        org = getattr(request, "organization", None)
        if org:
            employee_orders = employee_orders.filter(organization=org)

        # A rep statement must not show an order as "No commission" when a commission
        # exists but was filtered out by a report/business-group scope.
        missed_commissions = (
            _commission_base_queryset(request)
            .filter(sale__order__in=employee_orders)
            .filter(profile_commission_q(profile, request.user.email))
            .exclude(pk__in=queryset.values("pk"))
        )
        if missed_commissions.exists():
            queryset = queryset | missed_commissions

    orders = []
    credits = []
    total_earned = Decimal("0.00")
    pending_payout = Decimal("0.00")
    paid_total = Decimal("0.00")
    totals_by_currency = {}
    payout_buckets = {
        status: {"count": 0, "amount": Decimal("0.00"), "currency_totals": {}}
        for status, _ in Commission.STATUS_CHOICES
    }

    for comm in queryset.order_by("sale__order__order_date", "id"):
        line = _statement_line_from_commission(comm, profile)
        amount = comm.commission_amount or Decimal("0.00")
        currency = line["currency"]
        bucket_totals = totals_by_currency.setdefault(
            currency,
            {
                "currency": currency,
                "total_commission_earned": Decimal("0.00"),
                "pending_payout": Decimal("0.00"),
                "paid_total": Decimal("0.00"),
            },
        )
        total_earned += amount
        bucket_totals["total_commission_earned"] += amount
        if comm.status == Commission.STATUS_PAID:
            paid_total += amount
            bucket_totals["paid_total"] += amount
        else:
            pending_payout += amount
            bucket_totals["pending_payout"] += amount

        bucket = payout_buckets.get(comm.status)
        if bucket is not None:
            bucket["count"] += 1
            bucket["amount"] += amount
            bucket["currency_totals"][currency] = (
                bucket["currency_totals"].get(currency, Decimal("0.00")) + amount
            )

        if line["line_type"] == "credit":
            credits.append(line)
        else:
            orders.append(line)

    commissioned_order_ids = {line["order_id"] for line in orders if line.get("order_id")}
    commissioned_months = {
        (line.get("period_start"), line.get("currency"))
        for line in orders
        if line.get("calculation_scope") == Commission.SCOPE_EMPLOYEE_MONTH
    }
    if profile_employee_id:
        order_qs = Order.objects.filter(employee_id=profile_employee_id)
        if start_date and end_date:
            order_qs = order_qs.filter(order_date__range=[start_date, end_date])
        org = getattr(request, "organization", None)
        if org:
            order_qs = order_qs.filter(organization=org)
        for order in order_qs.order_by("-order_date", "order_id"):
            if order.order_id in commissioned_order_ids:
                continue
            month_start = order.order_date.replace(day=1).isoformat()
            order_currency = normalize_currency(getattr(order, "currency", None))
            if (month_start, order_currency) in commissioned_months:
                continue
            orders.append(
                {
                    "id": None,
                    "order_id": order.order_id,
                    "order_date": str(order.order_date),
                    "product": order.product_name or order.service_name,
                    "sales_amount": str(order.sales_amount),
                    "commission_amount": "0.00",
                    "currency": normalize_currency(getattr(order, "currency", None)),
                    "commission_rate": None,
                    "status": "no_commission",
                    "plan_name": None,
                    "employee_name": profile.name if profile else None,
                    "employee_email": profile.email if profile else None,
                    "calculated_at": None,
                    "manager_approved_at": None,
                    "approved_at": None,
                    "paid_at": None,
                    "payout_run_id": None,
                    "line_type": "order",
                    "credit_reason": None,
                }
            )

    comm_ids = list(queryset.values_list("id", flat=True))
    adjustments = []
    if comm_ids:
        for dispute in CommissionDispute.objects.filter(
            commission_id__in=comm_ids
        ).select_related("commission", "commission__sale__order"):
            order = (
                dispute.commission.sale.order
                if dispute.commission.sale_id and dispute.commission.sale.order_id
                else None
            )
            adjustments.append(
                {
                    "id": dispute.id,
                    "commission_id": dispute.commission_id,
                    "order_id": order.order_id if order else None,
                    "message": dispute.message,
                    "status": dispute.status,
                    "resolution_message": dispute.resolution_message or "",
                    "created_at": dispute.created_at.isoformat(),
                    "resolved_at": (
                        dispute.resolved_at.isoformat() if dispute.resolved_at else None
                    ),
                    "commission_amount": str(dispute.commission.commission_amount),
                    "currency": normalize_currency(getattr(order, "currency", None)),
                }
            )

    payout_status = [
        {
            "status": status,
            "label": label,
            "count": payout_buckets[status]["count"],
            "amount": str(payout_buckets[status]["amount"]),
            "currency_summary": [
                {"currency": code, "amount": str(amount)}
                for code, amount in sorted(
                    payout_buckets[status]["currency_totals"].items()
                )
            ],
        }
        for status, label in Commission.STATUS_CHOICES
    ]

    all_lines = orders + credits
    currency_summary = [
        {
            "currency": code,
            "total_commission_earned": str(values["total_commission_earned"]),
            "pending_payout": str(values["pending_payout"]),
            "paid_total": str(values["paid_total"]),
        }
        for code, values in sorted(totals_by_currency.items())
    ]
    return Response(
        {
            "employee_name": profile.name if profile else request.user.email,
            "employee_id": profile.employee_id if profile else None,
            "employee_email": request.user.email,
            "personal_currency": (
                normalize_currency(profile.personal_currency)
                if profile
                else "INR"
            ),
            "position_name": profile.position_name if profile else None,
            "territory_name": (
                profile.territory.name if profile and profile.territory_id else None
            ),
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "summary": {
                "total_commission_earned": str(total_earned),
                "pending_payout": str(pending_payout),
                "paid_total": str(paid_total),
                "order_line_count": len(orders),
                "credit_count": len(credits),
                "adjustment_count": len(adjustments),
            },
            "currency_summary": currency_summary,
            "orders": orders,
            "credits": credits,
            "adjustments": adjustments,
            "payout_status": payout_status,
            "total_commission": str(total_earned),
            "line_count": len(all_lines),
            "lines": all_lines,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_statement_export(request):
    """CSV export of commission statement."""
    queryset = _commissions_for_user(request)
    queryset, start_date, end_date = _apply_commission_filters(queryset, request)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "commission_id",
        "order_id",
        "order_date",
        "product",
        "sales_amount",
        "commission_rate_pct",
        "commission_amount",
        "line_type",
        "status",
        "plan_name",
        "calculated_at",
        "manager_approved_at",
        "approved_at",
        "paid_at",
    ])
    profile = get_request_user_profile(request)
    profile_employee_id = profile.employee_id if profile else None
    for comm in queryset.order_by("period_start", "sale__order__order_date", "id"):
        order = comm.sale.order if comm.sale_id and comm.sale.order_id else None
        sales = (
            comm.source_sales_total
            if comm.calculation_scope == Commission.SCOPE_EMPLOYEE_MONTH
            else (order.sales_amount if order else None)
        )
        line_type = (
            "credit"
            if order
            and profile_employee_id
            and order.employee_id
            and order.employee_id != profile_employee_id
            and profile
            and comm.employee.email == profile.email
            else "order"
        )
        writer.writerow([
            comm.id,
            order.order_id if order else "Monthly summary",
            order.order_date if order else (comm.period_start or ""),
            order.service_name if order else "Monthly total",
            sales if sales is not None else "",
            _commission_rate_pct(comm.commission_amount, sales) or "",
            comm.commission_amount,
            line_type,
            comm.status,
            comm.compensation_plan.plan_name if comm.compensation_plan_id else "",
            comm.calculated_at,
            comm.manager_approved_at,
            comm.approved_at,
            comm.paid_at,
        ])

    from django.http import HttpResponse

    filename = f"commission-statement-{request.user.email.split('@')[0]}.csv"
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_manager_commissions_view(request):
    """Manager (or admin) approves calculated commissions."""
    if not (user_is_manager(request) or user_is_admin(request)):
        return Response({"error": "Only managers or admins can manager-approve"}, status=403)

    queryset, start_date, end_date, err = _parse_approval_body(request)
    if err:
        return err

    count = approve_manager_commissions(queryset, request.user)
    record_audit(request, "commissions_manager_approved", {
        "approved": count,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    })
    if count:
        notify_commission_manager_approved(count, start_date, end_date)
    return Response({"approved": count, "stage": "manager"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_finance_commissions_view(request):
    """Finance (or admin) approves manager-approved commissions."""
    if not (user_is_finance(request) or user_is_admin(request)):
        return Response({"error": "Only finance or admins can finance-approve"}, status=403)

    queryset, start_date, end_date, err = _parse_approval_body(request)
    if err:
        return err

    count = approve_finance_commissions(queryset, request.user)
    record_audit(request, "commissions_finance_approved", {
        "approved": count,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    })
    if count:
        notify_commission_finance_approved(count, start_date, end_date)
    return Response({"approved": count, "stage": "finance"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leaderboard(request):
    """Rank employees by commission earnings for a period."""
    queryset = _commission_base_queryset(request)
    org = getattr(request, "organization", None)
    if org:
        queryset = queryset.filter(organization=org)

    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = with_commission_currency(queryset)

    if not user_can_view_finance_data(request) and not user_is_manager(request):
        queryset = _commissions_for_user(request)

    from .list_scope import commission_employee_search_q, list_limit_for_request

    q = (request.query_params.get("q") or "").strip()
    if q:
        queryset = queryset.filter(commission_employee_search_q(q, organization=org))

    ranked = (
        queryset.values(
            "employee_id",
            "employee__name",
            "employee__email",
            "report_currency",
        )
        .annotate(
            total_commission=Sum("commission_amount"),
            deal_count=Count("id"),
        )
        .order_by("-total_commission")
    )

    limit = list_limit_for_request(request, searching=bool(q))
    total_count = ranked.count()

    results = []
    for idx, row in enumerate(ranked[:limit], start=1):
        profile = UserProfile.objects.filter(
            email__iexact=row["employee__email"],
            organization=getattr(request, "organization", None),
        ).first()
        results.append({
            "rank": idx,
            "employee_id": profile.employee_id if profile else None,
            "employee_name": row["employee__name"],
            "employee_email": row["employee__email"],
            "territory": profile.territory.name if profile and profile.territory_id else None,
            "total_commission": str(row["total_commission"] or 0),
            "deal_count": row["deal_count"],
            "currency": normalize_currency(row.get("report_currency")),
        })

    return Response({
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
        "results": results,
        "count": total_count,
        "limited": total_count > limit,
    })


class TerritoryViewSet(viewsets.ModelViewSet):
    serializer_class = TerritorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Territory.objects.all()
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_create(self, serializer):
        require_admin(self.request)
        org = getattr(self.request, "organization", None)
        instance = serializer.save(organization=org)
        record_audit(self.request, "territory_created", {"id": instance.pk, "code": instance.code})

    def perform_update(self, serializer):
        require_admin(self.request)
        instance = serializer.save()
        record_audit(self.request, "territory_updated", {"id": instance.pk})

    def perform_destroy(self, instance):
        require_admin(self.request)
        record_audit(self.request, "territory_deleted", {"id": instance.pk, "code": instance.code})
        instance.delete()


class PayoutRunViewSet(viewsets.ModelViewSet):
    serializer_class = PayoutRunSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        require_finance_or_admin(self.request)
        qs = PayoutRun.objects.select_related("created_by")
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_create(self, serializer):
        require_finance_or_admin(self.request)
        org = getattr(self.request, "organization", None)
        instance = serializer.save(organization=org, created_by=self.request.user)
        record_audit(self.request, "payout_run_created", {"id": instance.pk, "name": instance.name})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_payout_run_paid_view(request, run_id):
    """Mark a payout run as paid and update linked commissions."""
    require_finance_or_admin(request)
    org = getattr(request, "organization", None)
    payout_run = PayoutRun.objects.filter(pk=run_id, organization=org).first()
    if not payout_run:
        return Response({"error": "Payout run not found"}, status=404)
    if org and payout_run.organization_id != org.id:
        return Response({"error": "Forbidden"}, status=403)

    payment_reference = request.data.get("payment_reference", "")
    count = mark_payout_run_paid(payout_run, payment_reference, request.user)
    record_audit(request, "payout_run_paid", {
        "id": payout_run.pk,
        "commissions_paid": count,
        "payment_reference": payment_reference,
    })
    notify_commission_paid(payout_run, count)
    return Response({
        "id": payout_run.pk,
        "status": payout_run.status,
        "commissions_paid": count,
        "paid_at": payout_run.paid_at.isoformat() if payout_run.paid_at else None,
    })


class CommissionDisputeViewSet(viewsets.ModelViewSet):
    serializer_class = CommissionDisputeSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        qs = CommissionDispute.objects.select_related(
            "commission",
            "commission__employee",
            "raised_by",
            "resolved_by",
            "employee_acknowledged_by",
        )
        if user_can_view_finance_data(self.request) or user_is_manager(self.request):
            org = getattr(self.request, "organization", None)
            if org:
                qs = qs.filter(commission__organization=org)
            return qs.order_by("-created_at")

        comm_ids = _commissions_for_user(self.request).values_list("id", flat=True)
        return qs.filter(commission_id__in=comm_ids).order_by("-created_at")

    def perform_create(self, serializer):
        commission = serializer.validated_data["commission"]
        allowed = _commissions_for_user(self.request).filter(pk=commission.pk).exists()
        if not allowed and not user_can_view_finance_data(self.request):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot dispute this commission")

        if commission.disputes.filter(status=CommissionDispute.STATUS_OPEN).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"commission": "An open dispute already exists"})

        dispute = serializer.save(raised_by=self.request.user)
        record_audit(self.request, "commission_dispute_opened", {
            "dispute_id": dispute.pk,
            "commission_id": commission.pk,
        })
        notify_commission_dispute(dispute)

    def destroy(self, request, *args, **kwargs):
        dispute = self.get_object()
        if not _dispute_can_delete(dispute, request):
            return Response(
                {
                    "error": (
                        "Dispute can only be deleted after it is resolved or rejected "
                        "and the employee has acknowledged the outcome."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_audit(request, "commission_dispute_deleted", {
            "dispute_id": dispute.pk,
            "commission_id": dispute.commission_id,
        })
        dispute.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _dispute_is_closed(dispute):
    return dispute.status in (
        CommissionDispute.STATUS_RESOLVED,
        CommissionDispute.STATUS_REJECTED,
    )


def _user_can_access_dispute(request, dispute):
    if user_can_view_finance_data(request) or user_is_manager(request):
        org = getattr(request, "organization", None)
        if org:
            return dispute.commission.organization_id == org.id
        return True
    return _commissions_for_user(request).filter(pk=dispute.commission_id).exists()


def _dispute_can_acknowledge(dispute, request):
    if not _dispute_is_closed(dispute):
        return False
    if dispute.employee_acknowledged_at:
        return False
    return _commissions_for_user(request).filter(pk=dispute.commission_id).exists()


def _dispute_can_delete(dispute, request):
    if not _dispute_is_closed(dispute):
        return False
    if not dispute.employee_acknowledged_at:
        return False
    return _user_can_access_dispute(request, dispute)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resolve_commission_dispute(request, dispute_id):
    """Resolve or reject an open dispute (manager/finance/admin)."""
    if not (user_is_manager(request) or user_can_view_finance_data(request)):
        return Response({"error": "Forbidden"}, status=403)

    dispute = (
        CommissionDispute.objects.filter(
            pk=dispute_id,
            commission__organization=getattr(request, "organization", None),
        )
        .select_related("commission")
        .first()
    )
    if not dispute:
        return Response({"error": "Dispute not found"}, status=404)
    if dispute.status != CommissionDispute.STATUS_OPEN:
        return Response({"error": "Dispute is not open"}, status=400)

    new_status = (request.data.get("status") or CommissionDispute.STATUS_RESOLVED).lower()
    if new_status not in (CommissionDispute.STATUS_RESOLVED, CommissionDispute.STATUS_REJECTED):
        return Response({"error": "status must be resolved or rejected"}, status=400)

    from django.utils import timezone

    dispute.status = new_status
    dispute.resolution_message = request.data.get("resolution_message", "")
    dispute.resolved_by = request.user
    dispute.resolved_at = timezone.now()
    dispute.save()

    record_audit(request, "commission_dispute_resolved", {
        "dispute_id": dispute.pk,
        "status": new_status,
    })
    return Response(CommissionDisputeSerializer(dispute, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def acknowledge_commission_dispute(request, dispute_id):
    """Employee confirms they accept the resolved/rejected outcome."""
    dispute = (
        CommissionDispute.objects.filter(
            pk=dispute_id,
            commission__organization=getattr(request, "organization", None),
        )
        .select_related("commission", "commission__sale", "commission__sale__order")
        .first()
    )
    if not dispute:
        return Response({"error": "Dispute not found"}, status=404)
    if not _user_can_access_dispute(request, dispute):
        return Response({"error": "Forbidden"}, status=403)
    if not _dispute_can_acknowledge(dispute, request):
        return Response(
            {
                "error": (
                    "You can only acknowledge a dispute after admin has resolved or "
                    "rejected it, and before you have already acknowledged it."
                )
            },
            status=400,
        )

    from django.utils import timezone

    dispute.employee_acknowledged_at = timezone.now()
    dispute.employee_acknowledged_by = request.user
    dispute.save(update_fields=["employee_acknowledged_at", "employee_acknowledged_by"])

    record_audit(request, "commission_dispute_acknowledged", {
        "dispute_id": dispute.pk,
    })
    return Response(CommissionDisputeSerializer(dispute, context={"request": request}).data)


def _profile_display_name(profile):
    if not profile:
        return ""
    full = f"{profile.first_name} {profile.last_name}".strip()
    return full or (profile.name or "").strip() or profile.email


def _commission_breakdown(queryset, field_path, empty_label="Unassigned"):
    from .currencies import normalize_currency

    queryset = with_commission_currency(queryset)
    rows = (
        queryset.values(field_path, "report_currency")
        .annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
        .order_by("-total")
    )
    results = []
    for row in rows:
        label = row[field_path] or empty_label
        currency = normalize_currency(row["report_currency"])
        results.append(
            {
                "label": label,
                "currency": currency,
                "total_commission": float(row["total"] or 0),
                "count": row["count"],
            }
        )
    return results


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def advanced_analytics_report(request):
    """Territory, product, position splits, quota attainment, and growth leaders."""
    from datetime import date, timedelta

    queryset = _commission_base_queryset(request)
    org = getattr(request, "organization", None)
    if org:
        queryset = queryset.filter(organization=org)

    scoped_to_self = not user_can_view_finance_data(request) and not user_is_manager(request)
    if scoped_to_self:
        queryset = _commissions_for_user(request)

    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = with_commission_currency(queryset)

    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

    period_days = max((end_date - start_date).days + 1, 1)
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    by_territory = _commission_breakdown(queryset, "sale__order__territory__name")
    by_product = _commission_breakdown(
        queryset, "sale__order__service_name", empty_label="Unspecified product"
    )
    by_position = _commission_breakdown(queryset, "sale__order__position_name")

    orders_qs = Order.objects.filter(order_date__range=[start_date, end_date])
    if org:
        orders_qs = orders_qs.filter(organization=org)
    if scoped_to_self:
        profile = get_request_user_profile(request)
        if profile and profile.employee_id:
            orders_qs = orders_qs.filter(employee_id=profile.employee_id)
        else:
            orders_qs = orders_qs.none()

    sales_by_emp = orders_qs.values("employee_id", "currency").annotate(
        achievement=Sum("sales_amount"),
        order_count=Count("id"),
    )

    profiles = UserProfile.objects.exclude(employee_id="").exclude(
        employee_id__isnull=True
    )
    profiles = filter_queryset_by_organization(profiles, org)
    profile_map = {profile.employee_id: profile for profile in profiles}

    quota_vs_achievement = []
    attainment_values = []
    for row in sales_by_emp:
        emp_id = row["employee_id"]
        if not emp_id:
            continue
        profile = profile_map.get(emp_id)
        achievement = float(row["achievement"] or 0)
        quota = float(profile.personal_target if profile else 0)
        attainment_pct = round((achievement / quota) * 100, 1) if quota > 0 else None
        if attainment_pct is not None:
            attainment_values.append(attainment_pct)
        quota_vs_achievement.append(
            {
                "employee_id": emp_id,
                "employee_name": _profile_display_name(profile) if profile else emp_id,
                "quota": quota,
                "achievement": achievement,
                "attainment_pct": attainment_pct,
                "order_count": row["order_count"],
                "currency": normalize_currency(row.get("currency")),
                "personal_currency": normalize_currency(
                    row.get("currency") or (profile.personal_currency if profile else None)
                ),
            }
        )
    quota_vs_achievement.sort(key=lambda item: item["achievement"], reverse=True)

    avg_attainment_pct = (
        round(sum(attainment_values) / len(attainment_values), 1)
        if attainment_values
        else None
    )

    current_by_emp = queryset.values(
        "employee__email",
        "employee__name",
        "report_currency",
    ).annotate(
        current=Sum("commission_amount")
    )
    prev_queryset = _commission_base_queryset(request)
    if scoped_to_self:
        prev_queryset = _commissions_for_user(request)
    prev_queryset = prev_queryset.filter(commission_date_q(prev_start, prev_end))
    prev_queryset = with_commission_currency(prev_queryset)
    prev_by_email = {
        (row["employee__email"], normalize_currency(row.get("report_currency"))): float(row["previous"] or 0)
        for row in prev_queryset.values("employee__email", "report_currency").annotate(
            previous=Sum("commission_amount")
        )
    }

    top_growth_reps = []
    for row in current_by_emp:
        email = row["employee__email"]
        currency = normalize_currency(row.get("report_currency"))
        current = float(row["current"] or 0)
        previous = prev_by_email.get((email, currency), 0)
        if previous > 0:
            growth_pct = ((current - previous) / previous) * 100
        elif current > 0:
            growth_pct = 100.0
        else:
            growth_pct = 0.0
        profile = UserProfile.objects.filter(
            email__iexact=email,
            organization=org,
        ).first()
        top_growth_reps.append(
            {
                "employee_id": profile.employee_id if profile else None,
                "employee_name": row["employee__name"],
                "current_commission": current,
                "previous_commission": previous,
                "growth_pct": round(growth_pct, 1),
                "currency": currency,
            }
        )
    top_growth_reps.sort(key=lambda item: item["growth_pct"], reverse=True)

    return Response(
        {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "previous_start_date": str(prev_start),
            "previous_end_date": str(prev_end),
            "by_territory": by_territory[:12],
            "by_product": by_product[:12],
            "by_position": by_position[:12],
            "quota_vs_achievement": quota_vs_achievement[:20],
            "avg_attainment_pct": avg_attainment_pct,
            "top_growth_reps": top_growth_reps[:10],
        }
    )
