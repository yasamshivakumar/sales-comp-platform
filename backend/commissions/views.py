from datetime import datetime
from rest_framework import status
import csv
import io
import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework import viewsets
from .models import (
    Employee,
    Commission,
    UserProfile,
    HierarchyRelationship,
    CompensationPlan,
    CompensationTier,
    Order,
)
from decimal import Decimal, InvalidOperation
from .serializers import (
    EmployeeSerializer,
    CommissionSerializer,
    CompensationPlanSerializer,
    CompensationTierSerializer,
    OrderSerializer,
)
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from .serializers import UserProfileSerializer, HierarchyRelationshipSerializer
from django.conf import settings
from .services import (
    calculate_commission_for_order,
    approve_commissions,
    recalculate_orders_in_range,
)
from .permissions import (
    require_admin,
    require_finance_or_admin,
    user_is_admin,
    user_is_finance,
    user_is_manager,
    user_can_view_finance_data,
    get_request_user_profile,
)
from .audit import record_audit
from .emails import notify_admins, notify_user
from .invites import accept_invite, get_valid_invite, invite_context
from .models import AuditLog, ImportJob
from .imports import process_orders_csv, process_users_csv, should_use_async_import
from .tenants import filter_queryset_by_organization, get_profile_for_user
from .authentication import issue_user_token, token_expires_at_iso
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils import timezone

logger = logging.getLogger("commissions")


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return filter_queryset_by_organization(
            Employee.objects.all(),
            getattr(self.request, "organization", None),
        )

    def perform_create(self, serializer):
        require_admin(self.request)
        serializer.save(organization=getattr(self.request, "organization", None))

    def perform_update(self, serializer):
        require_admin(self.request)
        serializer.save(organization=getattr(self.request, "organization", None))

    def perform_destroy(self, instance):
        require_admin(self.request)
        instance.delete()


class CommissionViewSet(viewsets.ModelViewSet):
    serializer_class = CommissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q

        from .enterprise_views import _commission_base_queryset, commission_date_q
        from .list_scope import commission_employee_search_q
        from .user_scope import profile_commission_q

        queryset = _commission_base_queryset(self.request)
        profile = get_request_user_profile(self.request)

        if not (
            user_can_view_finance_data(self.request)
            or user_is_manager(self.request)
        ):
            if profile:
                queryset = queryset.filter(
                    profile_commission_q(profile, self.request.user.email)
                )
            else:
                queryset = queryset.filter(
                    employee__email__iexact=self.request.user.email
                )

        org = getattr(self.request, "organization", None)
        if org:
            queryset = queryset.filter(
                Q(organization=org) | Q(sale__order__organization=org)
            ).distinct()

        status_filter = self.request.query_params.get("status")
        if status_filter in {choice[0] for choice in Commission.STATUS_CHOICES}:
            queryset = queryset.filter(status=status_filter)

        start_date = parse_date(self.request.query_params.get("start_date") or "")
        end_date = parse_date(self.request.query_params.get("end_date") or "")
        if start_date and end_date:
            queryset = queryset.filter(commission_date_q(start_date, end_date))

        search = (self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                commission_employee_search_q(search, organization=org)
            )

        limit = self.request.query_params.get("limit")
        if limit:
            try:
                queryset = queryset[: int(limit)]
            except (TypeError, ValueError):
                pass

        return queryset.order_by("-calculated_at", "-id")

    def perform_create(self, serializer):
        # Commissions are engine-generated; manual writes are a finance/admin
        # action. Without this a rep could POST arbitrary commission_amounts.
        require_finance_or_admin(self.request)
        serializer.save(organization=getattr(self.request, "organization", None))

    def perform_update(self, serializer):
        require_finance_or_admin(self.request)
        serializer.save()

    def perform_destroy(self, instance):
        require_finance_or_admin(self.request)
        instance.delete()


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def signup(request):
    """Public self-signup is disabled — accounts are invite-only via User Setup."""
    return Response(
        {
            "error": (
                "Public signup is disabled. Ask your administrator to invite you "
                "from User Setup."
            ),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


signup.throttle_scope = "login"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def book_demo_request(request):
    """Public marketing form endpoint that emails demo requests to the sales inbox."""
    data = request.data or {}
    # Honeypot: bots often fill hidden fields; accept silently without emailing.
    if str(data.get("website") or data.get("company_url") or "").strip():
        return Response({"message": "Demo request sent successfully."})

    name = str(data.get("name") or "").strip()[:200]
    email = str(data.get("email") or "").strip().lower()[:254]
    company = str(data.get("company") or "").strip()[:200]
    phone = str(data.get("phone") or "").strip()[:40]
    message = str(data.get("message") or "").strip()[:2000]

    if not name:
        return Response({"error": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not email:
        return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_email(email)
    except ValidationError:
        return Response({"error": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)

    recipient = getattr(settings, "DEMO_REQUEST_EMAIL", "shivakumar@incentra.co.in")
    subject = f"[Incentra] Demo request from {name}"
    body = (
        "New demo request from the Incentra marketing website.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Company: {company or 'Not provided'}\n"
        f"Phone: {phone or 'Not provided'}\n\n"
        f"Message:\n{message or 'Not provided'}\n"
    )
    sent = notify_user(recipient, subject, body)
    if not sent:
        return Response(
            {
                "error": "Email service is temporarily unavailable. Please contact us directly.",
                "contact_email": recipient,
                "contact_phone": "8499087617",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response({"message": "Demo request sent successfully."})


book_demo_request.throttle_scope = "demo"


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def invite_detail(request, token):
    invite = get_valid_invite(token)
    if not invite:
        return Response(
            {"error": "Invite is invalid, expired, or already used."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from .people_ops import mark_invite_opened

    mark_invite_opened(invite)
    return Response(invite_context(invite))


invite_detail.throttle_scope = "login"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def invite_accept(request, token):
    password = request.data.get("password") or ""
    confirm_password = request.data.get("confirm_password") or password
    if len(password) < 8:
        return Response(
            {"error": "Password must be at least 8 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if password != confirm_password:
        return Response(
            {"error": "Password and confirmation do not match."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Enforce the configured AUTH_PASSWORD_VALIDATORS on invite acceptance too.
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(password)
    except DjangoValidationError as exc:
        return Response(
            {"error": " ".join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = accept_invite(token, password)
    if not user:
        return Response(
            {"error": "Invite is invalid, expired, or already used."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    record_audit(
        request,
        "invite_accepted",
        {"email": user.email, "user_id": user.id},
    )
    return Response({"message": "Password set successfully. You can now sign in."})


invite_accept.throttle_scope = "login"


class CompensationPlanListCreateView(generics.ListCreateAPIView):
    serializer_class = CompensationPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from .plan_catalog import apply_plan_list_filters

        qs = CompensationPlan.objects.prefetch_related(
            "versions",
            "versions__sc_rate_tables",
            "versions__sc_flat_rate_tables",
            "versions__sc_lookup_tables",
            "versions__commission_rules",
            "versions__quotas",
            "sc_rate_tables",
            "sc_flat_rate_tables",
            "sc_lookup_tables",
            "commission_rules",
        ).select_related("last_modified_by").order_by("-created_at")
        qs = filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )
        return apply_plan_list_filters(qs, self.request.query_params)

    def perform_create(self, serializer):
        plan = serializer.save(organization=getattr(self.request, "organization", None))
        record_audit(
            self.request,
            "compensation_plan_created",
            {
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "commission_table_type": plan.commission_table_type,
            },
        )

    def check_admin_permission(self, request):
        """Check if user is admin, raise PermissionDenied if not"""
        try:
            user_profile = UserProfile.objects.get(email=request.user.email)
            is_admin = user_profile.role.lower() in ['admin', 'administrator']
            if not is_admin:
                raise PermissionDenied("Only administrators can access compensation plans")
        except UserProfile.DoesNotExist:
            raise PermissionDenied("User profile not found")
        return True

    def list(self, request, *args, **kwargs):
        """Only admins can view compensation plans. Optional pagination."""
        self.check_admin_permission(request)
        queryset = self.filter_queryset(self.get_queryset())
        try:
            page_size = int(request.query_params.get("page_size") or 0)
        except (TypeError, ValueError):
            page_size = 0
        try:
            page = max(1, int(request.query_params.get("page") or 1))
        except (TypeError, ValueError):
            page = 1

        health = (request.query_params.get("health") or "").strip().lower()
        calc_filter = (request.query_params.get("calculation_status") or "").strip().lower()
        approval_filter = (request.query_params.get("approval_status") or "").strip().lower()
        readiness_min = (request.query_params.get("readiness_min") or "").strip()

        def _apply_health(rows):
            out = rows
            if health:
                if health in ("attention", "needs_attention"):
                    out = [
                        row
                        for row in out
                        if (row.get("health") or {}).get("level") in ("warning", "critical")
                    ]
                else:
                    out = [
                        row
                        for row in out
                        if (row.get("health") or {}).get("level") == health
                    ]
            if calc_filter:
                out = [
                    row
                    for row in out
                    if (row.get("calculation_status") or {}).get("status") == calc_filter
                ]
            if approval_filter:
                out = [
                    row
                    for row in out
                    if str(row.get("approval_status") or "").lower().replace(" ", "_")
                    == approval_filter
                    or str(row.get("approval_status") or "").lower() == approval_filter
                ]
            if readiness_min != "":
                try:
                    threshold = int(readiness_min)
                except ValueError:
                    threshold = None
                if threshold is not None:
                    if threshold == 0:
                        out = [
                            row
                            for row in out
                            if (row.get("health") or {}).get("score", 100) < 40
                        ]
                    else:
                        out = [
                            row
                            for row in out
                            if (row.get("health") or {}).get("score", 0) >= threshold
                        ]
            return out

        if page_size > 0:
            page_size = min(page_size, 200)
            # When filtering by health, evaluate a bounded window then page in memory.
            if health:
                serializer = self.get_serializer(queryset[:500], many=True)
                filtered = _apply_health(serializer.data)
                total = len(filtered)
                start = (page - 1) * page_size
                page_rows = filtered[start : start + page_size]
            else:
                total = queryset.count()
                start = (page - 1) * page_size
                end = start + page_size
                page_qs = queryset[start:end]
                page_rows = self.get_serializer(page_qs, many=True).data
            return Response(
                {
                    "count": total,
                    "page": page,
                    "page_size": page_size,
                    "results": page_rows,
                }
            )

        serializer = self.get_serializer(queryset, many=True)
        data = _apply_health(serializer.data)
        return Response(data)

    def create(self, request, *args, **kwargs):
        """Only admins can create compensation plans"""
        self.check_admin_permission(request)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only admins can delete compensation plans"""
        self.check_admin_permission(request)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Only admins can update compensation plans"""
        self.check_admin_permission(request)
        return super().update(request, *args, **kwargs)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compensation_plans_search(request):
    """
    GET /api/compensation-plans/search/?q= — cross-entity catalog search.
    Returns plans, versions, rules, rate bands, and participant hits.
    """
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can access compensation plans")
    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return Response({"q": q, "results": []})

    from .models import CommissionPlanVersion, CommissionRule, SCRateTable
    from .plan_catalog import apply_plan_list_filters

    org = getattr(request, "organization", None)
    plans = apply_plan_list_filters(
        filter_queryset_by_organization(CompensationPlan.objects.all(), org),
        {"q": q},
    )[:15]

    results = []
    for plan in plans:
        results.append(
            {
                "type": "plan",
                "id": plan.id,
                "label": plan.plan_name,
                "href": f"/comp-plans/{plan.id}/overview",
                "meta": plan.role or plan.business_group or "",
            }
        )

    version_qs = CommissionPlanVersion.objects.filter(
        Q(description__icontains=q)
        | Q(role__icontains=q)
        | Q(position_name__icontains=q)
        | Q(business_group__icontains=q)
    ).select_related("compensation_plan")
    if org is not None:
        version_qs = version_qs.filter(organization=org)
    for v in version_qs[:10]:
        results.append(
            {
                "type": "version",
                "id": v.id,
                "label": f"{v.compensation_plan.plan_name} v{v.version_number}",
                "href": f"/comp-plans/{v.compensation_plan_id}/versions",
                "meta": v.status,
            }
        )

    rules = CommissionRule.objects.filter(name__icontains=q).select_related(
        "compensation_plan"
    )
    if org is not None:
        rules = rules.filter(organization=org)
    for rule in rules[:10]:
        if not rule.compensation_plan_id:
            continue
        results.append(
            {
                "type": "rule",
                "id": rule.id,
                "label": rule.name,
                "href": f"/comp-plans/{rule.compensation_plan_id}/rules",
                "meta": rule.rule_type,
            }
        )

    rates = SCRateTable.objects.filter(tier_name__icontains=q).select_related(
        "compensation_plan"
    )
    if org is not None:
        rates = rates.filter(compensation_plan__organization=org)
    for row in rates[:10]:
        if not row.compensation_plan_id:
            continue
        results.append(
            {
                "type": "rate_table",
                "id": row.id,
                "label": row.tier_name or f"Rate {row.id}",
                "href": f"/comp-plans/{row.compensation_plan_id}/rates",
                "meta": f"{row.commission_rate}%",
            }
        )

    profiles = UserProfile.objects.filter(
        Q(name__icontains=q) | Q(email__icontains=q) | Q(employee_id__icontains=q)
    )
    if org is not None:
        profiles = profiles.filter(organization=org)
    for p in profiles[:10]:
        results.append(
            {
                "type": "participant",
                "id": p.id,
                "label": p.name or p.email,
                "href": "/comp-plans",
                "meta": p.role or p.position_name or "",
            }
        )

    return Response({"q": q, "count": len(results), "results": results[:40]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compensation_plans_summary(request):
    """GET /api/compensation-plans/summary/ — catalog KPI strip."""
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can access compensation plans")
    from .plan_catalog import build_catalog_summary

    return Response(build_catalog_summary(getattr(request, "organization", None)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compensation_plan_participants(request, pk):
    """GET /api/compensation-plans/<id>/participants/ — matched employees."""
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can access compensation plans")
    from .plan_catalog import participants_queryset_for_plan

    org = getattr(request, "organization", None)
    qs = CompensationPlan.objects.all()
    qs = filter_queryset_by_organization(qs, org)
    try:
        plan = qs.get(pk=pk)
    except CompensationPlan.DoesNotExist:
        return Response({"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)

    profiles = participants_queryset_for_plan(plan, org)
    q = (request.query_params.get("q") or "").strip()
    if q:
        profiles = profiles.filter(
            Q(name__icontains=q)
            | Q(email__icontains=q)
            | Q(employee_id__icontains=q)
            | Q(role__icontains=q)
            | Q(position_name__icontains=q)
            | Q(business_group__icontains=q)
            | Q(function_name__icontains=q)
            | Q(market__icontains=q)
            | Q(title__icontains=q)
            | Q(hierarchy__icontains=q)
            | Q(territory__name__icontains=q)
        )

    business_group = (request.query_params.get("business_group") or "").strip()
    if business_group:
        profiles = profiles.filter(business_group__iexact=business_group)
    department = (request.query_params.get("department") or "").strip()
    if department:
        profiles = profiles.filter(function_name__iexact=department)
    region = (request.query_params.get("region") or "").strip()
    if region:
        profiles = profiles.filter(
            Q(market__iexact=region) | Q(territory__name__iexact=region)
        )

    from .plan_catalog import build_coverage_summary
    from .models import Commission

    coverage = build_coverage_summary(plan, org)

    total = profiles.count()
    try:
        page_size = int(request.query_params.get("page_size") or 50)
    except (TypeError, ValueError):
        page_size = 50
    page_size = max(1, min(page_size, 200))
    try:
        page = max(1, int(request.query_params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    start = (page - 1) * page_size
    rows = list(profiles.select_related("territory")[start : start + page_size])
    emails = [p.email for p in rows if p.email]
    emp_by_email = {
        e.email.lower(): e.id
        for e in Employee.objects.filter(email__in=emails)
    }
    latest_comm = {}
    if emp_by_email:
        for c in (
            Commission.objects.filter(
                compensation_plan=plan,
                employee_id__in=list(emp_by_email.values()),
            )
            .order_by("employee_id", "-calculated_at")
            .only("employee_id", "commission_amount", "calculated_at")
        ):
            if c.employee_id not in latest_comm:
                latest_comm[c.employee_id] = float(c.commission_amount)

    # Current month quota from display version if present
    from .plan_versions import display_version_for_plan

    version = display_version_for_plan(plan)
    month_quota = None
    if version is not None:
        today = timezone.localdate()
        qrow = version.quotas.filter(year=today.year, month=today.month).first()
        if qrow:
            month_quota = float(qrow.quota_amount)

    results = []
    for p in rows:
        target = float(p.personal_target or 0)
        emp_id = emp_by_email.get((p.email or "").lower())
        commission = latest_comm.get(emp_id) if emp_id else None
        attainment = None
        if target > 0 and commission is not None:
            # Rough proxy: commission relative to target * sample — show target attainment
            # using sales isn't available here; leave null unless we have sales.
            attainment = None
        results.append(
            {
                "id": p.id,
                "name": p.name or f"{p.first_name} {p.last_name}".strip() or p.email,
                "email": p.email,
                "employee_id": p.employee_id or "",
                "role": p.role or "",
                "position_name": p.position_name or "",
                "business_group": p.business_group or "",
                "title": p.title or "",
                "department": p.function_name or "",
                "region": p.market or (p.territory.name if p.territory_id else ""),
                "manager": p.hierarchy or "",
                "territory_name": p.territory.name if p.territory_id else "",
                "current_quota": month_quota if month_quota is not None else target,
                "personal_target": target,
                "current_attainment": attainment,
                "current_commission": commission,
            }
        )
    return Response(
        {
            "count": total,
            "page": page,
            "page_size": page_size,
            "plan_id": plan.id,
            "match": "position_name" if (plan.position_name or "").strip() else "role",
            "coverage": coverage,
            "results": results,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compensation_plan_activity(request, pk):
    """GET /api/compensation-plans/<id>/activity/ — recent plan actions."""
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can access compensation plans")
    from .plan_catalog import plan_activity_queryset, serialize_activity_row

    org = getattr(request, "organization", None)
    qs = CompensationPlan.objects.all()
    qs = filter_queryset_by_organization(qs, org)
    try:
        plan = qs.get(pk=pk)
    except CompensationPlan.DoesNotExist:
        return Response({"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        limit = min(int(request.query_params.get("limit") or 40), 200)
    except (TypeError, ValueError):
        limit = 40
    rows = list(plan_activity_queryset(plan, org)[:limit])
    return Response(
        {
            "count": len(rows),
            "plan_id": plan.id,
            "results": [serialize_activity_row(row) for row in rows],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compensation_plan_insights(request, pk):
    """GET /api/compensation-plans/<id>/insights/ — lightweight plan analytics."""
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can access compensation plans")
    from .plan_catalog import build_plan_insights

    org = getattr(request, "organization", None)
    qs = CompensationPlan.objects.all()
    qs = filter_queryset_by_organization(qs, org)
    try:
        plan = qs.get(pk=pk)
    except CompensationPlan.DoesNotExist:
        return Response({"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(build_plan_insights(plan, org))


class CompensationPlanDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CompensationPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["enterprise_full"] = True
        return ctx

    def get_queryset(self):
        qs = CompensationPlan.objects.prefetch_related(
            "versions",
            "versions__sc_rate_tables",
            "versions__sc_flat_rate_tables",
            "versions__sc_lookup_tables",
            "versions__commission_rules",
            "versions__commission_rules__conditions",
            "versions__commission_rules__results",
            "sc_rate_tables",
            "sc_flat_rate_tables",
            "sc_lookup_tables",
            "commission_rules",
            "commission_rules__conditions",
            "commission_rules__results",
        )
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def check_admin_permission(self, request):
        if not user_is_admin(request):
            raise PermissionDenied("Only administrators can access compensation plans")
        return True

    def retrieve(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        response = super().update(request, *args, **kwargs)
        plan = self.get_object()
        record_audit(
            request,
            "compensation_plan_updated",
            {
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "commission_table_type": plan.commission_table_type,
            },
        )
        return response

    def partial_update(self, request, *args, **kwargs):
        self.check_admin_permission(request)
        response = super().partial_update(request, *args, **kwargs)
        plan = self.get_object()
        record_audit(
            request,
            "compensation_plan_updated",
            {
                "plan_id": plan.id,
                "plan_name": plan.plan_name,
                "commission_table_type": plan.commission_table_type,
            },
        )
        return response


class UserProfileListCreateView(generics.ListCreateAPIView):

    queryset = UserProfile.objects.all().order_by('first_name')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Tenant isolation: only ever list the caller's own organization.
        qs = filter_queryset_by_organization(
            UserProfile.objects.select_related("territory", "assigned_compensation_plan")
            .prefetch_related("login_invites")
            .order_by("first_name", "name", "email"),
            getattr(self.request, "organization", None),
        )
        params = self.request.query_params
        q = (params.get("q") or params.get("search") or "").strip()
        if q:
            from .list_scope import profile_search_q
            from .models import HierarchyRelationship

            qs = qs.filter(
                profile_search_q(q)
                | Q(territory__name__icontains=q)
                | Q(territory__code__icontains=q)
                | Q(
                    id__in=HierarchyRelationship.objects.filter(
                        is_active=True,
                        parent_participant__name__icontains=q,
                    ).values_list("child_participant_id", flat=True)
                )
                | Q(
                    id__in=HierarchyRelationship.objects.filter(
                        is_active=True,
                        parent_participant__email__icontains=q,
                    ).values_list("child_participant_id", flat=True)
                )
            )
        role = (params.get("role") or "").strip()
        if role:
            qs = qs.filter(role__iexact=role)
        department = (params.get("department") or "").strip()
        if department:
            qs = qs.filter(
                Q(department__icontains=department) | Q(function_name__icontains=department)
            )
        business_group = (params.get("business_group") or params.get("business_unit") or "").strip()
        if business_group:
            qs = qs.filter(business_group__icontains=business_group)
        region = (params.get("region") or "").strip()
        if region:
            qs = qs.filter(market__icontains=region)
        territory = (params.get("territory") or "").strip()
        if territory:
            qs = qs.filter(
                Q(territory__name__icontains=territory) | Q(territory__code__icontains=territory)
            )
        eligibility = (params.get("eligibility") or "").strip().lower()
        if eligibility in ("eligible", "1", "true", "yes"):
            qs = qs.filter(commission_eligible=True)
        elif eligibility in ("not_eligible", "0", "false", "no"):
            qs = qs.filter(commission_eligible=False)
        manager = (params.get("manager") or "").strip()
        if manager:
            from .models import HierarchyRelationship

            qs = qs.filter(
                id__in=HierarchyRelationship.objects.filter(
                    is_active=True,
                )
                .filter(
                    Q(parent_participant__name__icontains=manager)
                    | Q(parent_participant__email__icontains=manager)
                    | Q(parent_participant__employee_id__icontains=manager)
                )
                .values_list("child_participant_id", flat=True)
            )
        plan = (params.get("plan") or params.get("compensation_plan") or "").strip()
        if plan:
            from .models import CompensationPlan

            org = getattr(self.request, "organization", None)
            plan_qs = CompensationPlan.objects.filter(status="Active")
            if org is not None:
                plan_qs = plan_qs.filter(organization=org)
            matched = plan_qs.filter(
                Q(plan_name__icontains=plan) | Q(position_name__icontains=plan) | Q(role__icontains=plan)
            )
            positions = [p for p in matched.values_list("position_name", flat=True) if p]
            roles = [r for r in matched.values_list("role", flat=True) if r]
            plan_filter = Q()
            if positions:
                plan_filter |= Q(position_name__in=positions)
            if roles:
                plan_filter |= Q(role__in=roles)
            if plan_filter:
                qs = qs.filter(plan_filter)
            else:
                qs = qs.none()
        view = (params.get("view") or "").strip().lower()
        if view in ("sales", "sales_participants"):
            qs = qs.filter(Q(role__icontains="Sales") | Q(role__iexact="Sales Rep"))
        elif view in ("managers", "manager"):
            qs = qs.filter(role__icontains="Manager")
        elif view in ("admins", "admin"):
            qs = qs.filter(role__iexact="Admin")
        ordering = (params.get("ordering") or params.get("sort") or "").strip()
        if ordering:
            from .people_ops import SORTABLE_FIELDS

            desc = ordering.startswith("-")
            key = ordering.lstrip("-")
            field = SORTABLE_FIELDS.get(key)
            if field:
                qs = qs.order_by(f"-{field}" if desc else field)
        return qs

    def list(self, request, *args, **kwargs):
        # User Setup is an admin screen; reps must not enumerate the org roster.
        require_admin(request)
        org = getattr(request, "organization", None)
        qs = self.filter_queryset(self.get_queryset())
        try:
            page = max(1, int(request.query_params.get("page") or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(200, max(1, int(request.query_params.get("page_size") or 50)))
        except (TypeError, ValueError):
            page_size = 50

        # Status / pending views need enrichment first — load capped set then filter.
        status_filter = (request.query_params.get("status") or "").strip().lower()
        view = (request.query_params.get("view") or "").strip().lower()
        needs_status_pass = bool(status_filter) or view in (
            "pending",
            "pending_invitations",
            "inactive",
            "inactive_users",
            "plan_assigned",
        )

        from .people_ops import enrich_people_row, resolve_plan_for_profile

        if needs_status_pass:
            profiles = list(qs[:2000])
        else:
            total = qs.count()
            start = (page - 1) * page_size
            profiles = list(qs[start : start + page_size])

        profile_ids = [p.id for p in profiles]
        manager_by_child = {}
        if profile_ids:
            for rel in HierarchyRelationship.objects.filter(
                child_participant_id__in=profile_ids,
                is_active=True,
            ).select_related("parent_participant"):
                manager_by_child[rel.child_participant_id] = rel.parent_participant

        rows = []
        for profile in profiles:
            manager = manager_by_child.get(profile.id)
            plan = resolve_plan_for_profile(profile, org)
            row = enrich_people_row(profile, manager=manager, plan=plan)
            if status_filter and row["status"] != status_filter:
                continue
            if view in ("pending", "pending_invitations"):
                if row["status"] not in ("pending_activation", "invited"):
                    continue
            if view in ("inactive", "inactive_users"):
                if row["status"] not in ("inactive", "suspended"):
                    continue
            if view in ("plan_assigned",):
                if row["status"] != "plan_assigned":
                    continue
            rows.append(row)

        if needs_status_pass:
            total = len(rows)
            start = (page - 1) * page_size
            rows = rows[start : start + page_size]
        else:
            total = qs.count()

        return Response(
            {
                "results": rows,
                "count": total,
                "page": page,
                "page_size": page_size,
            }
        )

    def create(self, request, *args, **kwargs):
        # Only admins may create/update profiles. Without this, any user could
        # POST their own email with role=Admin and escalate their privileges.
        require_admin(request)

        try:
            data = request.data.copy()

            # ---------------------------------------------------
            # Required Field
            # ---------------------------------------------------
            email = str(
                data.get('email', '')
            ).strip()

            if not email:
                return Response(
                    {'error': 'Email is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from .field_rules import (
                find_user_profile_duplicates,
                validate_user_profile_fields,
            )
            from rest_framework.exceptions import ValidationError as DRFValidationError

            try:
                validate_user_profile_fields(data)
            except DRFValidationError as exc:
                detail = exc.detail
                if isinstance(detail, dict):
                    detail = "; ".join(
                        f"{k}: {v[0] if isinstance(v, list) else v}"
                        for k, v in detail.items()
                    )
                return Response({"error": str(detail)}, status=status.HTTP_400_BAD_REQUEST)

            # ---------------------------------------------------
            # Boolean Conversion
            # ---------------------------------------------------
            enable_login = str(
                data.get('enable_login', 'False')
            ).strip().lower() in ['true', '1', 'yes']

            # ---------------------------------------------------
            # Numeric Fields
            # ---------------------------------------------------
            personal_target = (
                data.get('personal_target') or 0
            )

            split_percentage = (
                data.get('split_percentage') or 100
            )

            # ---------------------------------------------------
            # Username
            # ---------------------------------------------------
            username = str(
                data.get('username', '')
            ).strip()

            if not username:
                username = email

            employee_id_val = str(data.get('employee_id', '')).strip()
            org = getattr(request, "organization", None)

            # Reject duplicate email / employee_id within the org (create-only).
            dup_errors = find_user_profile_duplicates(
                org, email, employee_id_val
            )
            if dup_errors:
                return Response(
                    {"error": " ".join(dup_errors)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ---------------------------------------------------
            # Create UserProfile
            # ---------------------------------------------------
            profile = UserProfile.objects.create(
                email=email,
                organization=org,
                enable_login=enable_login,
                name=str(data.get('name', '')).strip(),
                role=str(data.get('role', 'Sales Rep')).strip(),
                username=username,
                first_name=str(data.get('first_name', '')).strip(),
                last_name=str(data.get('last_name', '')).strip(),
                prefix=str(data.get('prefix', '')).strip(),
                employee_id=employee_id_val,
                hire_date=data.get('hire_date'),
                personal_target=personal_target,
                personal_currency=str(
                    data.get('personal_currency', 'INR')
                ).strip(),
                business_group=str(
                    data.get('business_group', 'India')
                ).strip(),
                market=str(
                    data.get('region') or data.get('market') or ''
                ).strip(),
                title=str(data.get('title', '')).strip(),
                pay_period_type=str(
                    data.get('pay_period_type', 'Monthly')
                ).strip(),
                position_name=str(data.get('position_name', '')).strip(),
                position_title=str(data.get('position_title', '')).strip(),
                department=str(
                    data.get("department") or data.get("function_name") or ""
                ).strip(),
                phone=str(data.get("phone") or "").strip(),
                commission_eligible=str(
                    data.get("commission_eligible", "true")
                ).strip().lower()
                in ("true", "1", "yes", ""),
            )
            created = True

            territory_raw = data.get("territory") or data.get("territory_id")
            if territory_raw not in ("", None):
                from .integrations.user_import import resolve_or_create_territory_id

                try:
                    territory_pk = resolve_or_create_territory_id(
                        org, territory_raw, create_if_missing=True
                    )
                except ValueError as exc:
                    return Response(
                        {"error": str(exc)},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                profile.territory_id = territory_pk
                profile.save(update_fields=["territory_id"])
            elif "territory" in data or "territory_id" in data:
                profile.territory = None
                profile.save(update_fields=["territory"])

            # ---------------------------------------------------
            # Login: invite-only activation (no password until accepted)
            # ---------------------------------------------------
            invite_status = ""
            invite_link = ""
            invite_error = ""
            if enable_login:
                from .invites import build_invite_url, create_user_invite

                _invite, token, sent, invite_error = create_user_invite(
                    profile, invited_by=request.user
                )
                if sent:
                    invite_status = "sent"
                elif token:
                    invite_status = "created"
                    invite_link = build_invite_url(token)
                else:
                    invite_status = "email_failed"

            # ---------------------------------------------------
            # Hierarchy Relationship
            # ---------------------------------------------------
            parent_participant = data.get(
                'parent_participant'
            )

            child_participant = data.get(
                'child_participant'
            )

            if parent_participant and child_participant:

                # Scope by org so hierarchy cannot reference another tenant's profiles.
                parent_profile = UserProfile.objects.filter(
                    id=parent_participant, organization=org
                ).first()

                child_profile = UserProfile.objects.filter(
                    id=child_participant, organization=org
                ).first()

                if parent_profile and child_profile:

                    HierarchyRelationship.objects.update_or_create(
                        parent_participant=parent_profile,
                        child_participant=child_profile,
                        defaults={
                            'split_percentage': split_percentage,
                            'is_active': True,
                        }
                    )

            serializer = self.get_serializer(profile)
            payload = dict(serializer.data)
            if invite_status:
                payload["invite_status"] = invite_status
            if invite_link:
                payload["invite_link"] = invite_link
            if invite_error:
                payload["invite_error"] = invite_error

            record_audit(
                request,
                "user_setup_created" if created else "user_setup_updated",
                {
                    "profile_id": profile.id,
                    "email": profile.email,
                    "employee_id": profile.employee_id,
                    "role": profile.role,
                    "enable_login": profile.enable_login,
                    "invite_status": invite_status or None,
                },
            )

            return Response(
                payload,
                status=status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            )

        except Exception as e:

            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PeopleSummaryView(APIView):
    """GET /api/user-setup/summary/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        require_admin(request)
        from .people_ops import build_people_summary

        org = getattr(request, "organization", None)
        qs = filter_queryset_by_organization(UserProfile.objects.all(), org)
        return Response(build_people_summary(org, qs))


class PeopleDetailView(APIView):
    """GET/PATCH /api/user-setup/<pk>/ — People workspace."""

    permission_classes = [IsAuthenticated]

    def _get_profile(self, request, pk):
        org = getattr(request, "organization", None)
        return filter_queryset_by_organization(
            UserProfile.objects.select_related(
                "territory", "assigned_compensation_plan"
            ).prefetch_related("login_invites"),
            org,
        ).filter(pk=pk).first()

    def get(self, request, pk):
        require_admin(request)
        profile = self._get_profile(request, pk)
        if not profile:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)
        org = getattr(request, "organization", None)
        manager = _manager_for_profile(profile, org)
        from .people_ops import (
            PERMISSION_LABELS,
            SYSTEM_ROLES,
            build_commission_history,
            build_hierarchy_chain,
            build_participant_compensation,
            build_quota_attainment,
            build_sales_performance,
            enrich_people_row,
            resolve_plan_for_profile,
        )

        plan = resolve_plan_for_profile(profile, org)
        row = enrich_people_row(profile, manager=manager, plan=plan)
        # Direct reports
        reports = []
        for rel in HierarchyRelationship.objects.filter(
            parent_participant=profile, is_active=True
        ).select_related("child_participant")[:50]:
            child = rel.child_participant
            reports.append(
                {
                    "id": child.id,
                    "name": child.name or child.email,
                    "employee_id": child.employee_id,
                    "role": child.role,
                }
            )
        detail = serialize_user_profile_detail(profile, organization=org)
        detail.update(row)
        detail["direct_reports"] = reports
        detail["direct_report_count"] = len(reports)
        detail["hierarchy_chain"] = build_hierarchy_chain(profile, org)
        detail["participant_compensation"] = build_participant_compensation(
            profile, plan=plan, organization=org
        )
        detail["quota_attainment"] = build_quota_attainment(profile, org)
        detail["sales_performance"] = build_sales_performance(profile, org)
        detail["transactions"] = detail["sales_performance"]
        detail["assigned_plan"] = (
            {
                "id": plan.id,
                "plan_name": plan.plan_name,
                "status": plan.status,
            }
            if plan
            else None
        )
        detail["role_catalog"] = list(SYSTEM_ROLES)
        detail["permission_catalog"] = [
            {"code": k, "label": v} for k, v in PERMISSION_LABELS.items()
        ]
        detail["commission_history"] = build_commission_history(profile, org)
        detail["activity"] = []
        detail["audit_log"] = []
        from .models import AuditLog

        for log in AuditLog.objects.filter(organization=org).order_by("-created_at")[:120]:
            raw = getattr(log, "detail", None) or {}
            if not isinstance(raw, dict):
                continue
            if str(raw.get("profile_id") or "") == str(profile.id) or str(
                raw.get("email") or ""
            ).lower() == (profile.email or "").lower():
                entry = {
                    "id": log.id,
                    "action": log.action,
                    "user": log.user_email or getattr(log.user, "email", None) or "System",
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                    "details": raw,
                }
                detail["activity"].append(entry)
                detail["audit_log"].append(entry)
            if len(detail["audit_log"]) >= 40:
                break
        return Response(detail)

    def patch(self, request, pk):
        require_admin(request)
        profile = self._get_profile(request, pk)
        if not profile:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        # Prevent privilege escalation into Admin unless already Admin-capable caller
        # (require_admin already enforced). Still block empty role wipe.
        new_role = data.get("role")
        if new_role is not None and not str(new_role).strip():
            return Response({"error": "Role cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)

        old_role = profile.role
        old_quota = str(profile.personal_target)
        old_plan_id = profile.assigned_compensation_plan_id

        updatable = [
            "name",
            "first_name",
            "last_name",
            "role",
            "phone",
            "department",
            "function_name",
            "position_name",
            "position_title",
            "title",
            "business_group",
            "market",
            "account_status",
            "employee_id",
            "pay_period_type",
        ]
        changed = []
        for field in updatable:
            if field in data:
                setattr(profile, field, data.get(field) or "")
                changed.append(field)
        if "region" in data and "market" not in data:
            profile.market = str(data.get("region") or "").strip()
            changed.append("market")
        if "commission_eligible" in data:
            profile.commission_eligible = bool(data.get("commission_eligible"))
            changed.append("commission_eligible")
        if "enable_login" in data:
            profile.enable_login = bool(data.get("enable_login"))
            changed.append("enable_login")
        if "personal_target" in data:
            profile.personal_target = data.get("personal_target") or 0
            changed.append("personal_target")
        if "comp_effective_date" in data or "effective_date" in data:
            raw_eff = data.get("comp_effective_date", data.get("effective_date"))
            if raw_eff in ("", None):
                profile.comp_effective_date = None
            else:
                from datetime import datetime as dt

                try:
                    profile.comp_effective_date = dt.strptime(
                        str(raw_eff)[:10], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    return Response(
                        {"error": "Invalid effective date (use YYYY-MM-DD)"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            changed.append("comp_effective_date")
        if "assigned_plan_id" in data or "compensation_plan_id" in data:
            from .models import CompensationPlan

            org = getattr(request, "organization", None)
            plan_id = data.get("assigned_plan_id", data.get("compensation_plan_id"))
            if plan_id in ("", None):
                profile.assigned_compensation_plan = None
            else:
                plan = CompensationPlan.objects.filter(
                    id=plan_id, organization=org
                ).first()
                if not plan:
                    return Response(
                        {"error": "Compensation plan not found"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                profile.assigned_compensation_plan = plan
                if plan.position_name and not profile.position_name:
                    profile.position_name = plan.position_name
                    changed.append("position_name")
            changed.append("assigned_compensation_plan")
        if "territory" in data or "territory_id" in data:
            from .integrations.user_import import resolve_or_create_territory_id

            org = getattr(request, "organization", None)
            territory_raw = data.get("territory", data.get("territory_id"))
            if territory_raw in ("", None):
                profile.territory = None
            else:
                try:
                    profile.territory_id = resolve_or_create_territory_id(
                        org, territory_raw, create_if_missing=True
                    )
                except ValueError as exc:
                    return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            changed.append("territory")
        if "custom_permissions" in data:
            from .people_ops import PERMISSION_LABELS

            raw = data.get("custom_permissions")
            if raw is None:
                profile.custom_permissions = []
            elif isinstance(raw, list):
                allowed = set(PERMISSION_LABELS.keys())
                profile.custom_permissions = [c for c in raw if c in allowed]
            else:
                return Response(
                    {"error": "custom_permissions must be a list"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            changed.append("custom_permissions")
        if changed:
            profile.save()
        # Manager assignment
        manager_id = data.get("manager_id") or data.get("parent_participant")
        if manager_id:
            org = getattr(request, "organization", None)
            manager = UserProfile.objects.filter(id=manager_id, organization=org).first()
            if manager and manager.id != profile.id:
                HierarchyRelationship.objects.update_or_create(
                    parent_participant=manager,
                    child_participant=profile,
                    defaults={"split_percentage": data.get("split_percentage") or 100, "is_active": True},
                )
                changed.append("manager")
        if "role" in changed and profile.role != old_role:
            record_audit(
                request,
                "role_changed",
                {
                    "profile_id": profile.id,
                    "email": profile.email,
                    "from": old_role,
                    "to": profile.role,
                },
            )
        if "personal_target" in changed and str(profile.personal_target) != old_quota:
            record_audit(
                request,
                "quota_changed",
                {
                    "profile_id": profile.id,
                    "email": profile.email,
                    "from": old_quota,
                    "to": str(profile.personal_target),
                },
            )
        if (
            "assigned_compensation_plan" in changed
            and profile.assigned_compensation_plan_id != old_plan_id
        ):
            record_audit(
                request,
                "plan_assigned",
                {
                    "profile_id": profile.id,
                    "email": profile.email,
                    "plan_id": profile.assigned_compensation_plan_id,
                    "plan_name": getattr(
                        profile.assigned_compensation_plan, "plan_name", None
                    ),
                },
            )
        record_audit(
            request,
            "people_profile_updated",
            {"profile_id": profile.id, "email": profile.email, "fields": changed},
        )
        return self.get(request, pk)


class PeopleInviteActionView(APIView):
    """POST /api/user-setup/<pk>/invite/  body: {action: resend|revoke|copy_link}"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        require_admin(request)
        org = getattr(request, "organization", None)
        profile = filter_queryset_by_organization(
            UserProfile.objects.all(), org
        ).filter(pk=pk).first()
        if not profile:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)
        action = (request.data.get("action") or "resend").strip().lower()
        if action == "revoke":
            from .people_ops import revoke_pending_invite

            n = revoke_pending_invite(profile)
            record_audit(
                request,
                "invite_revoked",
                {"profile_id": profile.id, "email": profile.email, "count": n},
            )
            return Response({"ok": True, "revoked": n})
        # resend or copy_link — mint a fresh token (plaintext cannot be recovered from hash)
        profile.enable_login = True
        profile.save(update_fields=["enable_login"])
        from .invites import build_invite_url, create_user_invite

        send_email = action != "copy_link"
        invite, token, sent, invite_error = create_user_invite(
            profile, invited_by=request.user, send_email=send_email
        )
        record_audit(
            request,
            "invite_link_copied" if action == "copy_link" else "invite_resent",
            {"profile_id": profile.id, "email": profile.email, "sent": sent},
        )
        payload = {
            "ok": True,
            "sent": sent,
            "invite_error": invite_error or "",
            "action": action,
        }
        if token:
            payload["invite_link"] = build_invite_url(token)
        return Response(payload)


class PeopleBulkActionView(APIView):
    """POST /api/user-setup/bulk/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        require_admin(request)
        action = (request.data.get("action") or "").strip().lower()
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids required"}, status=status.HTTP_400_BAD_REQUEST)
        org = getattr(request, "organization", None)
        qs = filter_queryset_by_organization(
            UserProfile.objects.select_related("territory", "assigned_compensation_plan"),
            org,
        ).filter(id__in=ids)
        updated = 0
        if action == "invite":
            from .invites import create_user_invite

            for profile in qs:
                profile.enable_login = True
                profile.save(update_fields=["enable_login"])
                create_user_invite(profile, invited_by=request.user)
                updated += 1
                record_audit(
                    request,
                    "invitation_sent",
                    {"profile_id": profile.id, "email": profile.email},
                )
        elif action == "assign_role":
            role = (request.data.get("role") or "").strip()
            if not role:
                return Response({"error": "role required"}, status=status.HTTP_400_BAD_REQUEST)
            for profile in qs:
                old = profile.role
                profile.role = role
                profile.save(update_fields=["role"])
                updated += 1
                record_audit(
                    request,
                    "role_changed",
                    {
                        "profile_id": profile.id,
                        "email": profile.email,
                        "from": old,
                        "to": role,
                    },
                )
        elif action == "assign_plan":
            from .models import CompensationPlan

            plan_id = request.data.get("plan_id") or request.data.get("compensation_plan_id")
            plan_name = (request.data.get("plan_name") or "").strip()
            plan = None
            if plan_id:
                plan = CompensationPlan.objects.filter(
                    id=plan_id, organization=org
                ).first()
            elif plan_name:
                plan = CompensationPlan.objects.filter(
                    organization=org, plan_name__iexact=plan_name
                ).first()
            if not plan:
                return Response(
                    {"error": "plan_id or plan_name required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for profile in qs:
                profile.assigned_compensation_plan = plan
                if plan.position_name and not profile.position_name:
                    profile.position_name = plan.position_name
                profile.save()
                updated += 1
                record_audit(
                    request,
                    "plan_assigned",
                    {
                        "profile_id": profile.id,
                        "email": profile.email,
                        "plan_id": plan.id,
                        "plan_name": plan.plan_name,
                    },
                )
        elif action == "update_quota":
            quota = request.data.get("quota")
            if quota in (None, ""):
                return Response({"error": "quota required"}, status=status.HTTP_400_BAD_REQUEST)
            effective = request.data.get("effective_date") or request.data.get(
                "comp_effective_date"
            )
            for profile in qs:
                old = str(profile.personal_target)
                profile.personal_target = quota
                fields = ["personal_target"]
                if effective:
                    from datetime import datetime as dt

                    try:
                        profile.comp_effective_date = dt.strptime(
                            str(effective)[:10], "%Y-%m-%d"
                        ).date()
                        fields.append("comp_effective_date")
                    except ValueError:
                        pass
                profile.save(update_fields=fields)
                updated += 1
                record_audit(
                    request,
                    "quota_changed",
                    {
                        "profile_id": profile.id,
                        "email": profile.email,
                        "from": old,
                        "to": str(quota),
                    },
                )
        elif action == "change_territory":
            from .integrations.user_import import resolve_or_create_territory_id

            territory_raw = request.data.get("territory") or request.data.get("territory_id")
            if territory_raw in (None, ""):
                return Response(
                    {"error": "territory required"}, status=status.HTTP_400_BAD_REQUEST
                )
            try:
                territory_pk = resolve_or_create_territory_id(
                    org, territory_raw, create_if_missing=True
                )
            except ValueError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            updated = qs.update(territory_id=territory_pk)
            record_audit(
                request,
                "territory_changed",
                {"count": updated, "territory_id": territory_pk, "ids": ids[:50]},
            )
        elif action == "deactivate":
            updated = qs.update(account_status="deactivated", enable_login=False)
        elif action == "set_eligibility":
            eligible = bool(request.data.get("commission_eligible", True))
            updated = qs.update(commission_eligible=eligible)
        elif action == "export":
            # Return CSV payload for selected participants
            import csv
            import io

            from .people_ops import enrich_people_row, resolve_plan_for_profile

            buffer = io.StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=[
                    "employee_id",
                    "name",
                    "email",
                    "role",
                    "position",
                    "department",
                    "business_unit",
                    "manager_name",
                    "region",
                    "territory",
                    "status",
                    "compensation_plan",
                    "quota",
                    "eligibility",
                ],
            )
            writer.writeheader()
            manager_by_child = {}
            profile_ids = list(qs.values_list("id", flat=True))
            for rel in HierarchyRelationship.objects.filter(
                child_participant_id__in=profile_ids, is_active=True
            ).select_related("parent_participant"):
                manager_by_child[rel.child_participant_id] = rel.parent_participant
            for profile in qs:
                plan = resolve_plan_for_profile(profile, org)
                row = enrich_people_row(
                    profile, manager=manager_by_child.get(profile.id), plan=plan
                )
                writer.writerow(
                    {
                        "employee_id": row["employee_id"],
                        "name": row["display_name"],
                        "email": row["email"],
                        "role": row["role"],
                        "position": row["position"],
                        "department": row["department"],
                        "business_unit": row["business_unit"],
                        "manager_name": row["manager_name"],
                        "region": row["region"],
                        "territory": row["territory_name"],
                        "status": row["status_label"],
                        "compensation_plan": row["compensation_plan"],
                        "quota": row["quota"],
                        "eligibility": row["compensation_eligibility"],
                    }
                )
            record_audit(
                request,
                "people_exported",
                {"count": len(profile_ids), "ids": ids[:50]},
            )
            return Response({"csv": buffer.getvalue(), "count": len(profile_ids)})
        else:
            return Response({"error": "Unsupported action"}, status=status.HTTP_400_BAD_REQUEST)
        if action not in ("change_territory", "export"):
            record_audit(
                request,
                "people_bulk_action",
                {"action": action, "count": updated, "ids": ids[:50]},
            )
        return Response({"updated": updated})


class UserProfileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload"

    def post(self, request):
        require_admin(request)
        if "file" not in request.FILES:
            return Response(
                {"error": "No file uploaded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only CSV files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = getattr(request, "organization", None)
        if not organization:
            return Response(
                {"error": "Organization context missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .security import CsvValidationError, read_csv_upload

        try:
            decoded_file, rows = read_csv_upload(uploaded_file)
        except CsvValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if should_use_async_import(len(rows)):
            from .tasks import process_import_job_task

            job = ImportJob.objects.create(
                organization=organization,
                created_by=request.user,
                job_type=ImportJob.JOB_USERS,
                source_filename=uploaded_file.name,
                row_count=len(rows),
            )
            job.input_file.save(
                uploaded_file.name,
                ContentFile(decoded_file.encode("utf-8")),
                save=True,
            )
            process_import_job_task.delay(job.id)
            record_audit(
                request,
                "user_setup_upload_queued",
                {"job_id": job.id, "rows": len(rows), "filename": uploaded_file.name},
            )
            return Response(
                {
                    "message": "Import queued for background processing",
                    "async": True,
                    "job_id": job.id,
                    "status": job.status,
                    "row_count": len(rows),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        result = process_users_csv(organization, decoded_file)
        # Persist history even for synchronous imports
        job = ImportJob.objects.create(
            organization=organization,
            created_by=request.user,
            job_type=ImportJob.JOB_USERS,
            source_filename=uploaded_file.name,
            row_count=len(rows),
            status=ImportJob.STATUS_COMPLETED,
            result=result,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        try:
            job.input_file.save(
                uploaded_file.name,
                ContentFile(decoded_file.encode("utf-8")),
                save=True,
            )
        except Exception:
            pass
        payload = {
            "message": "Upload completed successfully",
            "job_id": job.id,
            **result,
        }
        if getattr(settings, "DEFAULT_ONBOARDING_PASSWORD", ""):
            payload["note"] = (
                "New login users received the password from DEFAULT_ONBOARDING_PASSWORD. "
                "Change it after first login."
            )
        record_audit(
            request,
            "user_setup_upload",
            {
                "success": result["success"],
                "failed": result["failed"],
                "filename": uploaded_file.name,
                "job_id": job.id,
            },
        )
        return Response(payload)


class UserProfileUploadValidateView(APIView):
    """POST /api/user-setup-upload/validate/ — dry-run CSV validation + preview."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload"

    def post(self, request):
        require_admin(request)
        if "file" not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        uploaded_file = request.FILES["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only CSV files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        org = getattr(request, "organization", None)
        if not org:
            return Response(
                {"error": "Organization context missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .security import CsvValidationError, read_csv_upload
        from .people_ops import validate_users_csv_rows

        try:
            _decoded, rows = read_csv_upload(uploaded_file)
        except CsvValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(validate_users_csv_rows(rows, org))


class UserProfileImportHistoryView(APIView):
    """GET /api/user-setup-upload/history/ — recent employee CSV imports."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        require_admin(request)
        org = getattr(request, "organization", None)
        qs = ImportJob.objects.filter(
            organization=org, job_type=ImportJob.JOB_USERS
        ).order_by("-created_at")[:30]
        rows = []
        for job in qs:
            result = job.result or {}
            rows.append(
                {
                    "id": job.id,
                    "filename": job.source_filename,
                    "status": job.status,
                    "row_count": job.row_count,
                    "success": result.get("success"),
                    "failed": result.get("failed"),
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "created_by": getattr(job.created_by, "email", None) or "",
                    "error_message": job.error_message or "",
                }
            )
        return Response({"results": rows, "count": len(rows)})


class HierarchyRelationshipListCreateView(generics.ListCreateAPIView):
    serializer_class = HierarchyRelationshipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # HierarchyRelationship has no org FK; scope through the participants.
        return filter_queryset_by_organization(
            HierarchyRelationship.objects.filter(is_active=True),
            getattr(self.request, "organization", None),
            field="child_participant__organization",
        ).order_by('parent_participant')

    def perform_create(self, serializer):
        require_admin(self.request)
        org = getattr(self.request, "organization", None)
        relationship = serializer.validated_data
        for side in ("parent_participant", "child_participant"):
            profile = relationship.get(side)
            if profile is not None and org is not None and profile.organization_id != org.id:
                raise PermissionDenied(
                    "Hierarchy participants must belong to your organization"
                )
        instance = serializer.save()
        record_audit(
            self.request,
            "hierarchy_created",
            {
                "id": instance.id,
                "parent_id": instance.parent_participant_id,
                "child_id": instance.child_participant_id,
                "split_percentage": str(instance.split_percentage),
            },
        )


class CompensationTierListCreateView(generics.ListCreateAPIView):
    serializer_class = CompensationTierSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # CompensationTier has no org FK; scope through its plan.
        return filter_queryset_by_organization(
            CompensationTier.objects.all(),
            getattr(self.request, "organization", None),
            field="plan__organization",
        ).order_by('plan', 'min_sales')

    def perform_create(self, serializer):
        require_admin(self.request)
        org = getattr(self.request, "organization", None)
        plan = serializer.validated_data.get("plan")
        if plan is not None and org is not None and plan.organization_id != org.id:
            raise PermissionDenied("Tier plan must belong to your organization")
        instance = serializer.save()
        record_audit(
            self.request,
            "compensation_tier_created",
            {
                "tier_id": instance.id,
                "plan_id": instance.plan_id,
                "min_sales": str(instance.min_sales),
                "commission_percent": str(instance.commission_percent),
            },
        )


def _orders_queryset_for_request(request):
    """Orders visible to the user, with commission data prefetched."""
    from .list_scope import order_search_q

    org = getattr(request, "organization", None)
    queryset = filter_queryset_by_organization(
        Order.objects.select_related("sale_record", "territory", "created_by")
        .prefetch_related(
            Prefetch(
                "sale_record__commission_set",
                queryset=filter_queryset_by_organization(
                    Commission.objects.select_related("compensation_plan").order_by("id"),
                    org,
                ),
            )
        )
        .order_by("-order_date", "-id"),
        org,
    )

    search_term = (
        request.query_params.get("q") or request.query_params.get("search") or ""
    ).strip()
    if search_term:
        queryset = queryset.filter(order_search_q(search_term))
    else:
        status_filter = (request.query_params.get("order_status") or "").strip()
        if status_filter:
            queryset = queryset.filter(order_status__iexact=status_filter)

    # Enterprise filters (additive)
    employee = (request.query_params.get("employee_id") or request.query_params.get("sales_rep") or "").strip()
    if employee:
        queryset = queryset.filter(employee_id__iexact=employee)
    region = (request.query_params.get("region") or "").strip()
    if region:
        queryset = queryset.filter(region__icontains=region)
    business_group = (request.query_params.get("business_group") or "").strip()
    if business_group:
        queryset = queryset.filter(business_group__icontains=business_group)
    product = (request.query_params.get("product") or "").strip()
    if product:
        queryset = queryset.filter(
            Q(product_name__icontains=product) | Q(service_name__icontains=product)
        )
    customer = (request.query_params.get("customer") or "").strip()
    if customer:
        queryset = queryset.filter(
            Q(customer_name__icontains=customer) | Q(customer_segment__icontains=customer)
        )
    source = (request.query_params.get("source") or "").strip()
    if source:
        queryset = queryset.filter(source__iexact=source)
    date_from = (request.query_params.get("date_from") or "").strip()
    if date_from:
        queryset = queryset.filter(order_date__gte=date_from)
    date_to = (request.query_params.get("date_to") or "").strip()
    if date_to:
        queryset = queryset.filter(order_date__lte=date_to)
    amount_min = (request.query_params.get("amount_min") or "").strip()
    if amount_min:
        queryset = queryset.filter(sales_amount__gte=amount_min)
    amount_max = (request.query_params.get("amount_max") or "").strip()
    if amount_max:
        queryset = queryset.filter(sales_amount__lte=amount_max)
    if (request.query_params.get("missing_rep") or "").strip() in ("1", "true", "yes"):
        queryset = queryset.filter(Q(employee_id__isnull=True) | Q(employee_id=""))

    user = request.user
    try:
        user_profile = get_profile_for_user(
            user,
            organization=getattr(request, "organization", None),
        )
        if not user_profile:
            raise UserProfile.DoesNotExist
        is_admin = user_profile.role.lower() in ["admin", "administrator"]
        if is_admin:
            return queryset
        if user_profile.employee_id:
            return queryset.filter(employee_id=user_profile.employee_id)
        return queryset.filter(employee_email=user.email)
    except UserProfile.DoesNotExist:
        return queryset.none()


class OrderListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/orders/   -> List all uploaded orders (filtered by role)
    POST /api/orders/   -> Create a single order manually
    
    Access Control:
    - Admin: Can see all orders, can create/update/delete orders
    - Regular employee: Can only see their own orders, cannot create/modify
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return _orders_queryset_for_request(self.request)

    def perform_create(self, serializer):
        # Matches the documented access control (and OrderDetailView updates):
        # only admins create orders; reps would otherwise be able to inject
        # orders that generate commissions for themselves.
        require_admin(self.request)
        order = serializer.save(
            organization=getattr(self.request, "organization", None),
            created_by=self.request.user,
            source=serializer.validated_data.get("source") or "manual",
        )
        calculate_commission_for_order(order)
        record_audit(
            self.request,
            "order_created",
            {
                "order_id": order.order_id,
                "employee_id": order.employee_id,
                "sales_amount": str(order.sales_amount),
                "order_status": order.order_status,
            },
        )


class OrderDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/orders/<id>/ — updates recalculate commission when eligible."""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _orders_queryset_for_request(self.request)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["include_workspace"] = True
        return ctx

    def perform_update(self, serializer):
        if not user_is_admin(self.request):
            raise PermissionDenied("Only administrators can update orders")
        instance = self.get_object()
        locked = str(instance.order_status or "").strip().lower() in (
            "success",
            "approved",
            "paid",
        )
        if locked:
            # Approved orders cannot silently change financial identity.
            protected = ("sales_amount", "employee_id", "order_date", "currency", "order_id")
            dirty = [
                field
                for field in protected
                if field in serializer.validated_data
                and serializer.validated_data.get(field) != getattr(instance, field)
            ]
            if dirty and not self.request.data.get("force_unlock"):
                raise PermissionDenied(
                    "Approved orders are locked. Unlock explicitly to change "
                    f"{', '.join(dirty)}."
                )
        order = serializer.save()
        calculate_commission_for_order(order)
        record_audit(
            self.request,
            "order_updated",
            {
                "order_id": order.order_id,
                "employee_id": order.employee_id,
                "sales_amount": str(order.sales_amount),
                "order_status": order.order_status,
            },
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        refreshed = (
            self.get_queryset()
            .select_related("sale_record")
            .prefetch_related("sale_record__commission_set")
            .get(pk=instance.pk)
        )
        return Response(self.get_serializer(refreshed).data)


class OrderSummaryView(APIView):
    """GET /api/orders/summary/ — Transaction Center KPIs + action center."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .transaction_ops import build_orders_summary

        org = getattr(request, "organization", None)
        base = filter_queryset_by_organization(
            Order.objects.select_related("sale_record").prefetch_related(
                "sale_record__commission_set"
            ),
            org,
        )
        if not user_is_admin(request):
            try:
                profile = get_profile_for_user(request.user, organization=org)
                if profile and profile.employee_id:
                    base = base.filter(employee_id=profile.employee_id)
            except Exception:
                pass
        return Response(build_orders_summary(org, base))


class OrderBulkActionView(APIView):
    """POST /api/orders/bulk/ — approve | reject | calculate | assign_rep."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        require_admin(request)
        action = (request.data.get("action") or "").strip().lower()
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids required"}, status=status.HTTP_400_BAD_REQUEST)

        qs = _orders_queryset_for_request(request).filter(id__in=ids)
        updated = 0
        results = []

        if action == "approve":
            for order in qs:
                order.order_status = "Success"
                order.save(update_fields=["order_status", "updated_at"])
                commission = calculate_commission_for_order(order)
                updated += 1
                results.append(
                    {
                        "id": order.id,
                        "order_id": order.order_id,
                        "has_commission": commission is not None,
                    }
                )
            record_audit(
                request,
                "orders_bulk_approved",
                {"order_ids": [o.order_id for o in qs], "count": updated},
            )
        elif action == "reject":
            for order in qs:
                order.order_status = "Rejected"
                order.save(update_fields=["order_status", "updated_at"])
                updated += 1
            record_audit(
                request,
                "orders_bulk_rejected",
                {"order_ids": [o.order_id for o in qs], "count": updated},
            )
        elif action == "calculate":
            for order in qs:
                if str(order.order_status).lower() != "success":
                    order.order_status = "Success"
                    order.save(update_fields=["order_status", "updated_at"])
                commission = calculate_commission_for_order(order)
                updated += 1
                results.append(
                    {
                        "id": order.id,
                        "order_id": order.order_id,
                        "has_commission": commission is not None,
                    }
                )
            record_audit(
                request,
                "orders_bulk_calculate",
                {"order_ids": [o.order_id for o in qs], "count": updated},
            )
        elif action == "assign_rep":
            employee_id = (request.data.get("employee_id") or "").strip()
            if not employee_id:
                return Response(
                    {"error": "employee_id required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for order in qs:
                if str(order.order_status).lower() in ("success", "approved", "paid"):
                    continue
                order.employee_id = employee_id
                credits = list(order.sales_credits or [])
                if not credits:
                    credits = [
                        {
                            "employee_id": employee_id,
                            "name": employee_id,
                            "role": "Primary Sales Rep",
                            "percent": 100,
                        }
                    ]
                else:
                    credits[0]["employee_id"] = employee_id
                    credits[0]["name"] = employee_id
                order.sales_credits = credits
                order.save(update_fields=["employee_id", "sales_credits", "updated_at"])
                updated += 1
            record_audit(
                request,
                "orders_bulk_assign_rep",
                {
                    "order_ids": [o.order_id for o in qs],
                    "employee_id": employee_id,
                    "count": updated,
                },
            )
        else:
            return Response(
                {"error": "Unsupported action"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"updated": updated, "results": results})


class OrderUploadValidateView(APIView):
    """POST /api/orders-upload/validate/ — dry-run CSV validation + preview."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        require_admin(request)
        if "file" not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        uploaded_file = request.FILES["file"]
        if not uploaded_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only CSV files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .security import CsvValidationError, read_csv_upload
        from .transaction_ops import validate_order_csv_rows

        try:
            _decoded, rows = read_csv_upload(uploaded_file)
        except CsvValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        org = getattr(request, "organization", None)
        return Response(validate_order_csv_rows(rows, org))


class OrderUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload"

    def post(self, request):
        # ---------------------------------------------------
        # Check file exists
        # ---------------------------------------------------
        if "file" not in request.FILES:
            return Response(
                {"error": "No file uploaded"},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES["file"]

        # ---------------------------------------------------
        # Support CSV files only
        # ---------------------------------------------------
        if not uploaded_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only CSV files are supported"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------------------------------------------------
        # Read CSV file (size/row limits enforced)
        # ---------------------------------------------------
        from .security import CsvValidationError, read_csv_upload

        try:
            decoded_file, rows = read_csv_upload(uploaded_file)
        except CsvValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        organization = getattr(request, "organization", None)
        if not organization:
            return Response(
                {"error": "Organization context missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if should_use_async_import(len(rows)):
            from .tasks import process_import_job_task

            job = ImportJob.objects.create(
                organization=organization,
                created_by=request.user,
                job_type=ImportJob.JOB_ORDERS,
                source_filename=uploaded_file.name,
                row_count=len(rows),
            )
            job.input_file.save(
                uploaded_file.name,
                ContentFile(decoded_file.encode("utf-8")),
                save=True,
            )
            process_import_job_task.delay(job.id)
            record_audit(
                request,
                "orders_upload_queued",
                {"job_id": job.id, "rows": len(rows), "filename": uploaded_file.name},
            )
            return Response(
                {
                    "message": "Import queued for background processing",
                    "async": True,
                    "job_id": job.id,
                    "status": job.status,
                    "row_count": len(rows),
                },
                status=status.HTTP_202_ACCEPTED,
            )

        summary = process_orders_csv(organization, decoded_file)
        record_audit(
            request,
            "orders_upload",
            {
                "success": summary["success"],
                "failed": summary["failed"],
                "filename": uploaded_file.name,
            },
        )
        notify_admins(
            "IncentivePro: order upload finished",
            (
                f"User: {request.user.email}\n"
                f"File: {uploaded_file.name}\n"
                f"Success: {summary['success']}\n"
                f"Failed: {summary['failed']}\n"
            ),
        )
        return Response({
            "message": "Order upload completed successfully",
            "async": False,
            **summary,
        })


# =====================================================
# Email-Based Login
# =====================================================
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def email_login(request):
    """
    Login endpoint that accepts email and password.
    
    Request body:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    
    Response:
    {
        "message": "Login successful",
        "token": "auth_token_here",
        "email": "user@example.com",
        "role": "Sales Rep",
        "user_id": 1
    }
    """
    from .security import (
        clear_login_failures,
        client_ip,
        login_locked_out,
        record_login_failure,
    )

    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password')
    ip = client_ip(request)
    user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:200]

    if not email or not password:
        return Response(
            {'error': 'Email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Account lockout: block after repeated failures for this email or IP.
    if login_locked_out(email, ip):
        logger.warning("Login locked out for %s from %s", email, ip)
        record_audit(
            request,
            "login_locked_out",
            {"email": email, "ip": ip, "user_agent": user_agent},
        )
        try:
            from .auth_hardening import record_login_event
            from .models import LoginEvent

            record_login_event(
                email=email,
                outcome=LoginEvent.OUTCOME_LOCKED,
                ip_address=ip,
                user_agent=user_agent,
            )
        except Exception:
            pass
        return Response(
            {'error': 'Too many failed attempts. Try again in a few minutes.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = (
        User.objects.filter(email=email).first()
        or User.objects.filter(username=email).first()
    )

    # Pending invite: block login until the invite is accepted / password set.
    if user is not None:
        from .invites import user_has_pending_invite

        if user_has_pending_invite(user):
            return Response(
                {
                    "error": (
                        "Please accept your invite and set a password "
                        "before signing in."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    # Uniform failure path for unknown user and wrong password so responses
    # (and password hashing time) cannot be used to enumerate accounts.
    if user is None or not user.check_password(
        password if user is not None else "-"
    ):
        if user is None:
            # Burn a hash to equalize timing with the wrong-password branch.
            User().set_password(password)
        record_login_failure(email, ip)
        logger.warning("Failed login for %s from %s", email, ip)
        record_audit(
            request,
            "login_failed",
            {"email": email, "ip": ip, "user_agent": user_agent},
        )
        try:
            from .auth_hardening import record_login_event
            from .models import LoginEvent

            record_login_event(
                email=email,
                user=user,
                outcome=LoginEvent.OUTCOME_FAILED,
                ip_address=ip,
                user_agent=user_agent,
            )
        except Exception:
            pass
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Check if user is active
    if not user.is_active:
        return Response(
            {'error': 'User account is inactive'},
            status=status.HTTP_403_FORBIDDEN
        )

    from .auth_hardening import (
        create_mfa_pending_token,
        issue_session_after_auth,
        mfa_required_for_login,
        record_login_event,
    )
    from .models import LoginEvent
    from .tenants import get_profile_for_user as _get_profile

    device_id = (request.headers.get("X-Device-Id") or request.data.get("device_id") or "")[:64]
    remember_device = bool(request.data.get("remember_device"))
    user_profile = _get_profile(user)
    org = user_profile.organization if user_profile else None

    try:
        if mfa_required_for_login(user, org, device_id):
            mfa_token = create_mfa_pending_token(
                user,
                ip=ip,
                user_agent=user_agent,
                device_id=device_id,
                remember=remember_device,
            )
            clear_login_failures(email, ip)
            record_login_event(
                organization=org,
                user=user,
                email=email,
                outcome=LoginEvent.OUTCOME_MFA_REQUIRED,
                ip_address=ip,
                user_agent=user_agent,
                device_id=device_id,
            )
            record_audit(
                request,
                "login_mfa_required",
                {"user_id": user.id, "email": email, "ip": ip},
                user=user,
                organization=org,
            )
            return Response(
                {
                    "mfa_required": True,
                    "mfa_token": mfa_token,
                    "email": user.email,
                    "message": "Enter the code from your authenticator app.",
                    "device_id": device_id,
                }
            )

        token, _session, flags = issue_session_after_auth(
            user,
            request=request,
            organization=org,
            device_id=device_id,
            remember_device_flag=remember_device,
            ip=ip,
            user_agent=user_agent,
        )
        clear_login_failures(email, ip)

        logger.info("Successful login for %s from %s", email, ip)
        record_audit(
            request,
            "login_success",
            {
                "user_id": user.id,
                "email": email,
                "ip": ip,
                "user_agent": user_agent,
                "suspicious": flags["suspicious"],
            },
            user=user,
            organization=org,
        )

        return Response({
            'message': 'Login successful',
            'token': token.key,
            'token_expires_at': flags["token_expires_at"],
            'email': user.email,
            'user_id': user.id,
            'role': user_profile.role if user_profile else 'Sales Rep',
            'name': user_profile.name if user_profile else user.get_full_name() or user.username,
            'must_change_password': flags["must_change_password"],
            'suspicious_login': flags["suspicious"],
            'device_id': device_id,
        })

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response(
            {'error': 'An error occurred during login'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =====================================================
# Change Password
# =====================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password endpoint.
    
    Request body:
    {
        "old_password": "current_password",
        "new_password": "new_password123"
    }
    
    Response:
    {
        "message": "Password changed successfully"
    }
    """
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response(
            {'error': 'Both old and new passwords are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(new_password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters long'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Enforce the configured AUTH_PASSWORD_VALIDATORS (common/numeric/similarity).
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        return Response(
            {'error': ' '.join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .auth_hardening import apply_password_update, password_in_history
    from .tenants import get_profile_for_user as _gp

    try:
        # Verify old password
        if not user.check_password(old_password):
            logger.warning(f"Failed password change attempt for user: {user.email}")
            return Response(
                {'error': 'Old password is incorrect'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        profile = _gp(user, organization=getattr(request, "organization", None))
        org = getattr(request, "organization", None) or (
            profile.organization if profile else None
        )
        if password_in_history(user, new_password):
            return Response(
                {'error': 'New password must not match a recently used password.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        apply_password_update(user, new_password, organization=org)

        # Invalidate all tokens to force re-login on other devices
        token = issue_user_token(user)
        from .auth_hardening import create_auth_session

        create_auth_session(
            user,
            token.key,
            organization=org,
            ip=None,
            user_agent="",
            device_id="",
        )
        record_audit(request, "password_changed", {"user_id": user.id})

        logger.info(f"Password changed successfully for user: {user.email}")

        return Response({
            'message': 'Password changed successfully',
            'token': token.key,
            'token_expires_at': token_expires_at_iso(token, organization=org),
            'must_change_password': False,
        })
        
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        return Response(
            {'error': 'An error occurred while changing password'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_status(request):
    """
    Idle-timeout keep-alive. Calling this while the user is active extends
    the backend session (sliding TTL) and returns the new expiry.
    """
    expires = getattr(request, "session_expires_at", None)
    if not expires and getattr(request, "auth", None) is not None:
        expires = token_expires_at_iso(
            request.auth, organization=getattr(request, "organization", None)
        )
    return Response({
        "token_expires_at": expires,
        "must_change_password": bool(getattr(request, "force_password_change", False)),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Server-side logout: revoke the caller's API token so it cannot be
    replayed after the client clears its own storage.
    """
    from .auth_hardening import revoke_auth_sessions_for_user

    revoke_auth_sessions_for_user(request.user, reason="logout")
    record_audit(request, "logout", {"user_id": request.user.id})
    return Response({"message": "Logged out"})


# =====================================================
# Get User Profile (for role-based access control)
# =====================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Get current user's profile and role information.
    
    Response:
    {
        "user_id": 1,
        "email": "user@example.com",
        "role": "Sales Rep",
        "name": "John Doe",
        "is_admin": false,
        "employee_id": "EMP001"
    }
    """
    user = request.user
    
    try:
        user_profile = UserProfile.objects.get(email=user.email)
        is_admin = user_profile.role.lower() in ['admin', 'administrator']
        
        org = user_profile.organization
        return Response({
            'user_id': user.id,
            'email': user.email,
            'role': user_profile.role,
            'name': user_profile.name,
            'is_admin': is_admin,
            'is_finance': user_is_finance(request),
            'is_manager': user_is_manager(request),
            'employee_id': user_profile.employee_id,
            'organization_slug': org.slug if org else None,
            'organization_name': org.name if org else None,
        })
        
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'User profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return Response(
            {'error': 'An error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =====================================================
# REPORTS API
# =====================================================

def _profile_display_name(profile):
    if not profile:
        return ""
    full = f"{profile.first_name} {profile.last_name}".strip()
    return full or (profile.name or "").strip() or profile.email


def _manager_for_profile(profile, organization=None):
    qs = HierarchyRelationship.objects.filter(
        child_participant=profile,
    ).select_related("parent_participant")
    if organization:
        qs = qs.filter(
            parent_participant__organization=organization,
            child_participant__organization=organization,
        )
    rel = qs.first()
    return rel.parent_participant if rel else None


def serialize_user_profile_detail(profile, *, organization=None):
    """Full imported employee profile for order forms and admin views."""
    manager = _manager_for_profile(profile, organization)
    territory = profile.territory
    return {
        "id": profile.id,
        "employee_id": profile.employee_id or "",
        "display_name": _profile_display_name(profile),
        "name": profile.name or "",
        "email": profile.email or "",
        "role": profile.role or "",
        "username": profile.username or "",
        "first_name": profile.first_name or "",
        "last_name": profile.last_name or "",
        "prefix": profile.prefix or "",
        "title": profile.title or "",
        "position_name": profile.position_name or "",
        "position_title": profile.position_title or "",
        "pay_period_type": profile.pay_period_type or "",
        "business_group": profile.business_group or "",
        "personal_target": str(profile.personal_target),
        "personal_currency": profile.personal_currency or "",
        "hire_date": profile.hire_date.isoformat() if profile.hire_date else "",
        "territory_id": profile.territory_id,
        "territory_name": territory.name if territory else "",
        "territory_code": territory.code if territory else "",
        "manager_name": _profile_display_name(manager) if manager else "",
        "manager_employee_id": manager.employee_id if manager else "",
        "hierarchy": profile.hierarchy or "",
        "function_name": profile.function_name or "",
        "title_category": profile.title_category or "",
        "level": profile.level or "",
        "market": profile.market or "",
        "region": profile.market or "",
        "enable_login": profile.enable_login,
        "crm_user_id": profile.crm_user_id or "",
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_user_detail(request, pk):
    """Return full imported employee profile for Create Order auto-fill."""
    org = getattr(request, "organization", None)
    profile = filter_queryset_by_organization(
        UserProfile.objects.select_related("territory"),
        org,
    ).filter(pk=pk).first()
    if not profile:
        return Response(
            {"error": "Employee profile not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(serialize_user_profile_detail(profile, organization=org))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_directory(request):
    """Employees for order-form search with position, manager, and territory."""
    from .list_scope import list_limit_for_request, profile_search_q

    org = getattr(request, "organization", None)
    profiles = filter_queryset_by_organization(
        UserProfile.objects.exclude(employee_id="")
        .exclude(employee_id__isnull=True)
        .select_related("territory"),
        org,
    ).order_by("employee_id")

    query = (request.query_params.get("q") or "").strip()
    if query:
        profiles = profiles.filter(profile_search_q(query))

    limit = list_limit_for_request(request, searching=bool(query))
    profile_list = list(profiles[:limit])
    profile_ids = [profile.id for profile in profile_list]
    manager_by_child = {}
    if profile_ids:
        for rel in HierarchyRelationship.objects.filter(
            child_participant_id__in=profile_ids
        ).filter(
            parent_participant__organization=org,
            child_participant__organization=org,
        ).select_related("parent_participant"):
            manager_by_child[rel.child_participant_id] = rel.parent_participant

    results = []
    for profile in profile_list:
        manager = manager_by_child.get(profile.id)
        results.append(
            {
                "id": profile.id,
                "employee_id": profile.employee_id,
                "display_name": _profile_display_name(profile),
                "position_name": profile.position_name or "",
                "business_group": profile.business_group or "",
                "manager_name": _profile_display_name(manager) if manager else "",
                "territory_id": profile.territory_id,
                "territory_name": profile.territory.name if profile.territory else "",
            }
        )

    return Response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def commission_summary_report(request):
    """
    Commission Summary Report
    Shows total commissions, top earners, metrics
    Admin: All employees, Employee: Own only
    """
    from django.db.models import Sum, Count, Avg
    from .currencies import active_currency_totals, normalize_currency
    from .enterprise_views import (
        _apply_commission_filters,
        _commission_base_queryset,
        with_commission_currency,
    )
    from .user_scope import profile_commission_q

    queryset = _commission_base_queryset(request)
    profile = get_request_user_profile(request)
    if not (user_can_view_finance_data(request) or user_is_admin(request)):
        if profile:
            queryset = queryset.filter(profile_commission_q(profile, request.user.email))
        else:
            queryset = queryset.none()

    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = with_commission_currency(queryset)

    totals_rows = list(
        queryset.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
    )
    commission_totals = [
        {
            "currency": normalize_currency(row["report_currency"]),
            "total": float(row["total"] or 0),
            "count": row["count"],
        }
        for row in totals_rows
    ]
    totals_by_currency = active_currency_totals(commission_totals)
    total_commission = sum(item["total"] for item in totals_by_currency)

    payout_record_count = queryset.count()
    active_reps_count = (
        queryset.filter(sale__order__employee_id__isnull=False)
        .values("sale__order__employee_id")
        .distinct()
        .count()
    )
    if active_reps_count == 0:
        active_reps_count = queryset.values("employee_id").distinct().count()

    avg_commission = queryset.aggregate(Avg("commission_amount"))["commission_amount__avg"] or 0

    top_earners = []
    if user_is_admin(request) or user_can_view_finance_data(request):
        top_earners = list(
            queryset.values("employee__name", "employee__email").annotate(
                total=Sum("commission_amount"),
                count=Count("id"),
            ).order_by("-total")[:5]
        )

    return Response({
        "total_commission": float(total_commission),
        "total_count": payout_record_count,
        "payout_record_count": payout_record_count,
        "active_reps_count": active_reps_count,
        "avg_commission": float(avg_commission),
        "top_earners": top_earners,
        "totals_by_currency": totals_by_currency,
        "is_admin": user_is_admin(request),
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_performance_report(request):
    """
    Sales Performance Report
    Shows sales by employee, achievement metrics
    """
    from django.db.models import Sum, Count
    from .business_groups import apply_business_group_to_orders, resolve_dashboard_business_group
    from .currencies import active_currency_totals, normalize_currency

    profile = get_request_user_profile(request)
    is_admin = user_is_admin(request) or user_can_view_finance_data(request)

    orders = filter_queryset_by_organization(
        Order.objects.all(),
        getattr(request, "organization", None),
    )

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    if start_date and end_date:
        orders = orders.filter(order_date__range=[start_date, end_date])

    if not is_admin:
        possible_employee_ids = []
        if profile and profile.employee_id:
            possible_employee_ids.append(profile.employee_id)
        orders = orders.filter(employee_id__in=possible_employee_ids)

    can_view_all_groups = user_is_admin(request) or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, profile, can_view_all_groups
    )
    orders = apply_business_group_to_orders(
        orders,
        effective_group,
        organization=getattr(request, "organization", None),
    )

    sales_data = list(
        orders.values("employee_id", "position_name").annotate(
            total_sales=Sum("sales_amount"),
            order_count=Count("id"),
            avg_order=Sum("sales_amount"),
        ).order_by("-total_sales")
    )

    currency_rows = list(
        orders.values("currency").annotate(
            total=Sum("sales_amount"),
            count=Count("id"),
        )
    )
    totals_by_currency = active_currency_totals(
        [
            {
                "currency": normalize_currency(row["currency"]),
                "total": float(row["total"] or 0),
                "count": row["count"],
            }
            for row in currency_rows
        ]
    )
    total_sales = sum(item["total"] for item in totals_by_currency)
    total_orders = orders.count()

    return Response({
        "total_sales": float(total_sales),
        "total_orders": total_orders,
        "sales_data": sales_data,
        "totals_by_currency": totals_by_currency,
        "is_admin": is_admin,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
    })


def _sales_breakdown(orders_qs, group_field, empty_label="Unspecified"):
    """Aggregate sales amount and order count by a field (+ currency)."""
    from django.db.models import Avg, Count, Sum

    from .currencies import normalize_currency

    rows = (
        orders_qs.values(group_field, "currency")
        .annotate(
            total_sales=Sum("sales_amount"),
            order_count=Count("id"),
            avg_order=Avg("sales_amount"),
        )
        .order_by("-total_sales")
    )
    results = []
    for row in rows:
        label = (row[group_field] or "").strip() or empty_label
        results.append(
            {
                "label": label,
                "currency": normalize_currency(row["currency"]),
                "total_sales": float(row["total_sales"] or 0),
                "order_count": row["order_count"],
                "avg_order": float(row["avg_order"] or 0),
            }
        )
    return results


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sales_by_region_report(request):
    """
    Sales insights breakdown by Order.region (e.g. Indian state) and Territory.

    Admin / finance / manager only.
    Query: start_date, end_date
    """
    from django.db.models import Count, Sum

    from .business_groups import apply_business_group_to_orders, resolve_dashboard_business_group
    from .currencies import active_currency_totals, normalize_currency

    if not (
        user_is_admin(request)
        or user_can_view_finance_data(request)
        or user_is_manager(request)
    ):
        raise PermissionDenied(
            "Only administrators, finance, or managers can view sales by analysis."
        )

    org = getattr(request, "organization", None)
    orders = filter_queryset_by_organization(Order.objects.all(), org)

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    if start_date and end_date:
        orders = orders.filter(order_date__range=[start_date, end_date])

    profile = get_request_user_profile(request)
    can_view_all_groups = user_is_admin(request) or user_is_finance(request)
    effective_group, _, _ = resolve_dashboard_business_group(
        request, profile, can_view_all_groups
    )
    orders = apply_business_group_to_orders(
        orders,
        effective_group,
        organization=org,
    )

    orders = orders.select_related("territory")

    by_region = _sales_breakdown(orders, "region", empty_label="Unspecified")
    # Annotate territory name via values on FK name
    by_territory_raw = (
        orders.values("territory__name", "currency")
        .annotate(
            total_sales=Sum("sales_amount"),
            order_count=Count("id"),
        )
        .order_by("-total_sales")
    )
    by_territory = []
    for row in by_territory_raw:
        by_territory.append(
            {
                "label": (row["territory__name"] or "").strip() or "Unspecified",
                "currency": normalize_currency(row["currency"]),
                "total_sales": float(row["total_sales"] or 0),
                "order_count": row["order_count"],
            }
        )

    # Combined breakdown so exports can show each territory next to its region.
    by_region_territory_raw = (
        orders.values("region", "territory__name", "currency")
        .annotate(
            total_sales=Sum("sales_amount"),
            order_count=Count("id"),
        )
        .order_by("region", "-total_sales")
    )
    by_region_territory = [
        {
            "region": (row["region"] or "").strip() or "Unspecified",
            "territory": (row["territory__name"] or "").strip() or "Unspecified",
            "currency": normalize_currency(row["currency"]),
            "total_sales": float(row["total_sales"] or 0),
            "order_count": row["order_count"],
        }
        for row in by_region_territory_raw
    ]

    currency_rows = list(
        orders.values("currency").annotate(
            total=Sum("sales_amount"),
            count=Count("id"),
        )
    )
    totals_by_currency = active_currency_totals(
        [
            {
                "currency": normalize_currency(row["currency"]),
                "total": float(row["total"] or 0),
                "count": row["count"],
            }
            for row in currency_rows
        ]
    )
    total_sales = sum(item["total"] for item in totals_by_currency)
    total_orders = orders.count()
    region_count = (
        orders.exclude(region__isnull=True)
        .exclude(region__exact="")
        .values("region")
        .distinct()
        .count()
    )

    # Share of total within primary currency bucket for table convenience
    primary_total = total_sales or 1
    for row in by_region:
        row["pct_of_total"] = round((row["total_sales"] / primary_total) * 100, 1) if primary_total else 0
    for row in by_territory:
        row["pct_of_total"] = round((row["total_sales"] / primary_total) * 100, 1) if primary_total else 0
    for row in by_region_territory:
        row["pct_of_total"] = round((row["total_sales"] / primary_total) * 100, 1) if primary_total else 0

    return Response(
        {
            "total_sales": float(total_sales),
            "total_orders": total_orders,
            "region_count": region_count,
            "totals_by_currency": totals_by_currency,
            "by_region": by_region,
            "by_territory": by_territory,
            "by_region_territory": by_region_territory,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "business_group": effective_group or "",
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_earnings_report(request):
    """
    Employee Earnings Report
    Detailed breakdown of commissions by employee.
    Supports the same date / business-group / employee search filters as
    the Performance dashboard leaderboard.
    """
    from django.db.models import Count, Sum

    from .currencies import normalize_currency
    from .enterprise_views import (
        _apply_commission_filters,
        _commission_base_queryset,
        _commissions_for_user,
        with_commission_currency,
    )
    from .list_scope import commission_employee_search_q, list_limit_for_request

    is_admin = user_is_admin(request)
    org = getattr(request, "organization", None)

    commissions = _commission_base_queryset(request)
    if org:
        commissions = commissions.filter(organization=org)

    if not user_can_view_finance_data(request) and not user_is_manager(request):
        commissions = _commissions_for_user(request)

    commissions, start_date, end_date = _apply_commission_filters(
        commissions, request
    )
    commissions = with_commission_currency(commissions)

    q = (request.query_params.get("q") or "").strip()
    if q:
        commissions = commissions.filter(
            commission_employee_search_q(q, organization=org)
        )

    ranked = (
        commissions.values(
            "employee_id",
            "employee__name",
            "employee__email",
            "report_currency",
        )
        .annotate(
            total_earnings=Sum("commission_amount"),
            commission_count=Count("id"),
        )
        .order_by("-total_earnings")
    )

    limit = list_limit_for_request(request, searching=bool(q))
    total_count = ranked.count()
    earnings_data = []
    for row in ranked[:limit]:
        earnings_data.append(
            {
                "employee_id": row["employee_id"],
                "employee__name": row["employee__name"],
                "employee_name": row["employee__name"],
                "employee__email": row["employee__email"],
                "employee_email": row["employee__email"],
                "total_earnings": str(row["total_earnings"] or 0),
                "total_commission": str(row["total_earnings"] or 0),
                "commission_count": row["commission_count"],
                "currency": normalize_currency(row.get("report_currency")),
            }
        )

    return Response(
        {
            "earnings": earnings_data,
            "is_admin": is_admin,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "count": total_count,
            "limited": total_count > limit,
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def period_analytics_report(request):
    """
    Period-wise Analytics Report
    Monthly, Quarterly, Annual metrics
    """
    from datetime import date, timedelta

    from dateutil.relativedelta import relativedelta
    from django.db.models import Count, Sum

    from .currencies import active_currency_totals, normalize_currency
    from .enterprise_views import (
        _apply_commission_filters,
        _commission_base_queryset,
        _commissions_for_user,
        commission_date_q,
        with_commission_currency,
    )

    queryset = _commission_base_queryset(request)
    if not (user_can_view_finance_data(request) or user_is_admin(request)):
        queryset = _commissions_for_user(request)

    queryset, start_date, end_date = _apply_commission_filters(queryset, request)
    queryset = with_commission_currency(queryset)

    period = request.query_params.get("period", "monthly")
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=365)

    period_data = []
    cursor = start_date.replace(day=1)

    while cursor <= end_date:
        if period == "quarterly":
            quarter = (cursor.month - 1) // 3
            bucket_start = date(cursor.year, quarter * 3 + 1, 1)
            bucket_end = bucket_start + relativedelta(months=3) - timedelta(days=1)
            label = f"Q{quarter + 1} {cursor.year}"
            cursor = bucket_start + relativedelta(months=3)
        elif period == "annual":
            bucket_start = date(cursor.year, 1, 1)
            bucket_end = date(cursor.year, 12, 31)
            label = str(cursor.year)
            cursor = date(cursor.year + 1, 1, 1)
        else:
            bucket_start = cursor
            bucket_end = (cursor + relativedelta(months=1)) - timedelta(days=1)
            label = cursor.strftime("%B %Y")
            cursor = cursor + relativedelta(months=1)

        if bucket_end < start_date or bucket_start > end_date:
            continue

        scoped = queryset.filter(commission_date_q(bucket_start, bucket_end))
        totals_rows = scoped.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
        bucket_total = sum(float(row["total"] or 0) for row in totals_rows)
        bucket_count = sum(row["count"] for row in totals_rows)
        period_data.append(
            {
                "period": label,
                "total": bucket_total,
                "count": bucket_count,
            }
        )

    totals_rows = list(
        queryset.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
    )
    totals_by_currency = active_currency_totals(
        [
            {
                "currency": normalize_currency(row["report_currency"]),
                "total": float(row["total"] or 0),
                "count": row["count"],
            }
            for row in totals_rows
        ]
    )

    return Response(
        {
            "period": period,
            "data": period_data,
            "totals_by_currency": totals_by_currency,
            "is_admin": user_is_admin(request),
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def command_center_report(request):
    """
    Sales Compensation Command Center aggregate.
    Additive endpoint — does not replace existing report APIs.
    """
    if not (
        user_is_admin(request)
        or user_can_view_finance_data(request)
        or user_is_manager(request)
    ):
        raise PermissionDenied(
            "Only administrators, finance, or managers can view the command center."
        )
    from .dashboard_ops import build_command_center

    return Response(build_command_center(request))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_transparency_report(request):
    """
    Drill-down: employee sales transactions + commissions + plan applied.
    Query: employee_id (required), optional start_date/end_date.
    """
    from django.db.models import Sum

    employee_id = (request.query_params.get("employee_id") or "").strip()
    if not employee_id:
        return Response(
            {"error": "employee_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    org = getattr(request, "organization", None)
    profile = get_request_user_profile(request)
    is_privileged = (
        user_is_admin(request)
        or user_can_view_finance_data(request)
        or user_is_manager(request)
    )
    if not is_privileged:
        if not profile or profile.employee_id != employee_id:
            raise PermissionDenied("You can only view your own transparency detail.")

    person = filter_queryset_by_organization(UserProfile.objects.all(), org).filter(
        employee_id=employee_id
    ).first()

    orders = filter_queryset_by_organization(Order.objects.all(), org).filter(
        employee_id=employee_id
    )
    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    if start_date and end_date:
        orders = orders.filter(order_date__range=[start_date, end_date])

    from .people_ops import resolve_plan_for_profile

    plan = resolve_plan_for_profile(person, org) if person else None

    txns = []
    for order in orders.order_by("-order_date")[:40]:
        commission = None
        try:
            sale = getattr(order, "sale_record", None)
            if sale:
                commission = (
                    Commission.objects.filter(sale=sale)
                    .select_related("compensation_plan")
                    .first()
                )
        except Exception:
            commission = None
        txns.append(
            {
                "order_id": order.order_id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "sales_amount": float(order.sales_amount or 0),
                "order_status": order.order_status,
                "plan_name": (
                    commission.compensation_plan.plan_name
                    if commission and commission.compensation_plan_id
                    else (plan.plan_name if plan else "")
                ),
                "calculation_method": (
                    str(getattr(plan, "tier_calculation_method", "") or "")
                    if plan
                    else ""
                ),
                "commission_amount": float(commission.commission_amount)
                if commission
                else None,
                "commission_status": commission.status if commission else None,
            }
        )

    total_sales = orders.aggregate(t=Sum("sales_amount"))["t"] or 0
    return Response(
        {
            "employee_id": employee_id,
            "employee_name": person.name if person else employee_id,
            "role": person.role if person else "",
            "assigned_plan": (
                {
                    "id": plan.id,
                    "plan_name": plan.plan_name,
                    "commission_table_type": plan.commission_table_type,
                    "tier_calculation_method": plan.tier_calculation_method,
                }
                if plan
                else None
            ),
            "total_sales": float(total_sales),
            "transactions": txns,
        }
    )


# =====================================================
# Phase 2: Approvals, payroll export, bulk recalc
# =====================================================

def _commission_queryset_for_export(request):
    """Base queryset for payroll export (admin/finance: own org; employee: own rows)."""
    from django.db.models import Q

    org = getattr(request, "organization", None)
    queryset = Commission.objects.select_related(
        "employee",
        "sale",
        "sale__order",
        "compensation_plan",
    )
    if org is None:
        return queryset.none()
    # Tenant isolation first: finance/admin only ever export their own org.
    queryset = queryset.filter(
        Q(organization=org) | Q(sale__order__organization=org)
    ).distinct()
    if user_can_view_finance_data(request):
        return queryset
    profile = get_request_user_profile(request)
    if not profile:
        return queryset.none()
    emails = [request.user.email]
    if profile.employee_id:
        emails.append(f"{profile.employee_id}@company.com")
    return queryset.filter(employee__email__in=emails)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_commissions_view(request):
    """
    Approve calculated commissions for payroll.

    Body: { "ids": [1,2,3] } and/or { "start_date": "2025-01-01", "end_date": "2025-01-31" }
    """
    from django.db.models import Q

    from .enterprise_views import commission_date_q

    require_admin(request)
    ids = request.data.get("ids") or []
    start_date = parse_date(request.data.get("start_date") or "")
    end_date = parse_date(request.data.get("end_date") or "")

    queryset = Commission.objects.filter(status=Commission.STATUS_CALCULATED)
    if ids:
        queryset = queryset.filter(id__in=ids)
    org = getattr(request, "organization", None)
    if org:
        queryset = queryset.filter(
            Q(organization=org) | Q(sale__order__organization=org)
        ).distinct()
    if start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
    if not ids and not (start_date and end_date):
        return Response(
            {"error": "Provide commission ids and/or start_date + end_date"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    count = approve_commissions(queryset, request.user)
    record_audit(
        request,
        "commissions_approved",
        {
            "approved": count,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "ids": ids,
        },
    )
    return Response({"approved": count})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_payroll_export(request):
    """
    CSV export for payroll (approved commissions by default).

    Query: start_date, end_date, status=approved|calculated|all
    """
    from .enterprise_views import commission_date_q

    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    status_param = (request.query_params.get("status") or "approved").lower()

    queryset = _commission_queryset_for_export(request)
    if start_date and end_date:
        queryset = queryset.filter(commission_date_q(start_date, end_date))
    if status_param == "approved":
        queryset = queryset.filter(status=Commission.STATUS_APPROVED)
    elif status_param == "calculated":
        queryset = queryset.filter(status=Commission.STATUS_CALCULATED)
    elif status_param != "all":
        return Response(
            {"error": "status must be approved, calculated, or all"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "commission_id",
        "employee_id",
        "employee_name",
        "employee_email",
        "order_id",
        "order_date",
        "sales_amount",
        "commission_amount",
        "status",
        "plan_name",
        "calculated_at",
        "approved_at",
    ])

    from .security import sanitize_csv_row

    for comm in queryset.order_by("sale__order__order_date", "employee__name"):
        order = comm.sale.order if comm.sale_id and comm.sale.order_id else None
        profile = UserProfile.objects.filter(email=comm.employee.email).first()
        writer.writerow(sanitize_csv_row([
            comm.id,
            profile.employee_id if profile else "",
            comm.employee.name,
            comm.employee.email,
            order.order_id if order else "",
            order.order_date.isoformat() if order and order.order_date else "",
            order.sales_amount if order else "",
            comm.commission_amount,
            comm.status,
            comm.compensation_plan.plan_name if comm.compensation_plan_id else "",
            comm.calculated_at.isoformat() if comm.calculated_at else "",
            comm.approved_at.isoformat() if comm.approved_at else "",
        ]))

    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payroll_commissions.csv"'
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def recalculate_commissions_view(request):
    """
    Recalculate commissions for orders in a date range (admin).

    Body: { "start_date": "2025-01-01", "end_date": "2025-01-31", "force": true }
    force=true replaces approved commissions; default skips approved orders.
    """
    require_admin(request)
    start_date = parse_date(request.data.get("start_date") or "")
    end_date = parse_date(request.data.get("end_date") or "")
    if not start_date or not end_date:
        return Response(
            {"error": "start_date and end_date are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    force_raw = request.data.get("force", False)
    if isinstance(force_raw, str):
        force = force_raw.strip().lower() in ("true", "1", "yes")
    else:
        force = bool(force_raw)
    stats = recalculate_orders_in_range(
        start_date,
        end_date,
        force=force,
        organization=getattr(request, "organization", None),
    )
    record_audit(
        request,
        "commissions_recalculated",
        {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "force": force,
            **stats,
        },
    )
    return Response(stats)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    """Recent audit events (admin / finance)."""
    require_finance_or_admin(request)
    limit = min(int(request.query_params.get("limit", 100)), 500)
    logs = AuditLog.objects.select_related("user", "plan_version").order_by("-created_at")
    logs = filter_queryset_by_organization(
        logs, getattr(request, "organization", None)
    )
    plan_id = (request.query_params.get("plan_id") or "").strip()
    if plan_id:
        logs = logs.filter(
            Q(plan_version__compensation_plan_id=plan_id)
            | Q(detail__plan_id=int(plan_id) if plan_id.isdigit() else plan_id)
            | Q(detail__plan_id=plan_id)
        )
    logs = logs[:limit]
    data = [
        {
            "id": row.id,
            "action": row.action,
            "user_email": row.user_email,
            "detail": row.detail,
            "ip_address": row.ip_address,
            "request_id": row.request_id,
            "plan_version_id": row.plan_version_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in logs
    ]
    return Response({"count": len(data), "results": data})


email_login.throttle_scope = "login"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def import_job_detail(request, job_id):
    """Poll status of a background CSV import."""
    org = getattr(request, "organization", None)
    job = ImportJob.objects.filter(pk=job_id, organization=org).first()
    if not job:
        return Response({"error": "Import job not found"}, status=status.HTTP_404_NOT_FOUND)

    if not user_is_admin(request) and job.created_by_id != request.user.id:
        return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

    return Response({
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "source_filename": job.source_filename,
        "row_count": job.row_count,
        "result": job.result,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_operations_summary(request):
    from .commission_ops import build_operations_summary

    return Response(build_operations_summary(request))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_operations_grid(request):
    from .commission_ops import build_operations_grid

    return Response(build_operations_grid(request))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_operations_detail(request):
    from .commission_ops import build_operations_detail

    data = build_operations_detail(request)
    if not data:
        return Response(
            {"error": "Commission record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def commission_operations_bulk(request):
    from .commission_ops import run_bulk_action

    result, err = run_bulk_action(request, request.data or {})
    if err:
        msg = err.get("error", "")
        code = (
            status.HTTP_403_FORBIDDEN
            if ("Only" in msg or "Insufficient" in msg)
            else status.HTTP_400_BAD_REQUEST
        )
        return Response(err, status=code)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def commission_adjustment_create(request):
    from .commission_ops import create_adjustment, _serialize_adjustment

    adj, err = create_adjustment(request, request.data or {})
    if err:
        msg = err.get("error", "")
        code = (
            status.HTTP_403_FORBIDDEN
            if "Only" in msg
            else status.HTTP_400_BAD_REQUEST
        )
        if "not found" in msg.lower():
            code = status.HTTP_404_NOT_FOUND
        return Response(err, status=code)
    return Response(_serialize_adjustment(adj), status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_operations_export(request):
    from .commission_ops import build_operations_export

    return build_operations_export(request)

