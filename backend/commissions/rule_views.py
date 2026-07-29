from .currencies import currency_choices_for_api

from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    CommissionPlanVersion,
    CommissionRule,
    CommissionRuleCondition,
    CommissionRuleResult,
    EmployeeCommissionRuleAssignment,
    UserProfile,
)
from .permissions import user_is_admin
from .rule_assignments import (
    add_rule_assignments,
    assignment_payload,
    employees_queryset_for_plan,
    find_invalid_assignments,
    remove_rule_assignments,
)
from .serializers import CommissionRuleSerializer
from .tenants import filter_queryset_by_organization


def _require_admin(request):
    if not user_is_admin(request):
        raise PermissionDenied("Only administrators can manage commission rules")


def _choice_list(choices):
    return [{"value": value, "label": label} for value, label in choices]


def _assert_version_editable(version):
    if version is None:
        return
    if version.status != CommissionPlanVersion.STATUS_DRAFT:
        raise ValidationError(
            f"Cannot modify rules on {version.status} version "
            f"{version.version_number}. Clone the version to edit."
        )


def _assignment_only_request(request):
    keys = set((request.data or {}).keys())
    return bool(keys) and keys.issubset({"assigned_employee_ids", "assigned_employees"})


class CommissionRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = CommissionRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _require_admin(self.request)
        qs = (
            CommissionRule.objects.select_related("compensation_plan", "plan_version")
            .prefetch_related(
                "conditions",
                "results",
                Prefetch(
                    "employee_assignments",
                    queryset=EmployeeCommissionRuleAssignment.objects.select_related(
                        "employee"
                    ),
                ),
            )
            .annotate(assignee_count=Count("employee_assignments", distinct=True))
        )
        qs = filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )
        plan_id = self.request.query_params.get("plan_id")
        if plan_id:
            qs = qs.filter(compensation_plan_id=plan_id)
        version_id = self.request.query_params.get("plan_version_id")
        if version_id:
            qs = qs.filter(plan_version_id=version_id)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs.order_by("sequence", "id")

    def perform_create(self, serializer):
        _require_admin(self.request)
        from .plan_versions import clone_version

        plan = serializer.validated_data.get("compensation_plan")
        version = serializer.validated_data.get("plan_version")

        if version is None and plan is not None:
            version = plan.versions.filter(
                status=CommissionPlanVersion.STATUS_DRAFT
            ).first()
            if version is None:
                source = (
                    plan.versions.filter(
                        status=CommissionPlanVersion.STATUS_PUBLISHED
                    )
                    .order_by("-version_number")
                    .first()
                    or plan.versions.order_by("-version_number").first()
                )
                if source is None:
                    raise ValidationError(
                        "This plan has no versions. Recreate the plan or contact support."
                    )
                version = clone_version(
                    source,
                    user=self.request.user,
                    description="Auto-created draft for rule edit.",
                )
        _assert_version_editable(version)
        serializer.save(
            organization=getattr(self.request, "organization", None),
            plan_version=version,
        )


class CommissionRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommissionRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _require_admin(self.request)
        qs = (
            CommissionRule.objects.select_related(
                "compensation_plan", "plan_version"
            )
            .prefetch_related(
                "conditions",
                "results",
                Prefetch(
                    "employee_assignments",
                    queryset=EmployeeCommissionRuleAssignment.objects.select_related(
                        "employee"
                    ),
                ),
            )
            .annotate(assignee_count=Count("employee_assignments", distinct=True))
        )
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_update(self, serializer):
        if not _assignment_only_request(self.request):
            _assert_version_editable(serializer.instance.plan_version)
        serializer.save()

    def perform_destroy(self, instance):
        _assert_version_editable(instance.plan_version)
        instance.delete()


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def commission_rule_employees(request, pk):
    """List, add, or remove employees assigned to a commission rule."""
    _require_admin(request)
    org = getattr(request, "organization", None)
    rule = get_object_or_404(
        filter_queryset_by_organization(
            CommissionRule.objects.select_related(
                "compensation_plan", "plan_version", "plan_version__compensation_plan"
            ),
            org,
        ),
        pk=pk,
    )

    if request.method == "GET":
        rows = (
            EmployeeCommissionRuleAssignment.objects.filter(rule=rule)
            .select_related("employee", "rule", "rule__compensation_plan", "rule__plan_version")
            .order_by("employee__name", "employee_id")
        )
        return Response([assignment_payload(row) for row in rows])

    employee_ids = request.data.get("employee_ids")
    if not isinstance(employee_ids, list):
        raise ValidationError({"employee_ids": "Provide a list of employee profile ids."})

    if request.method == "POST":
        added = add_rule_assignments(
            rule,
            employee_ids,
            organization=org,
            assigned_by=request.user,
        )
        return Response(
            {"added": added, "assignee_count": rule.employee_assignments.count()},
            status=status.HTTP_200_OK,
        )

    removed = remove_rule_assignments(rule, employee_ids)
    return Response(
        {"removed": removed, "assignee_count": rule.employee_assignments.count()}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_rule_eligible_employees(request):
    """
    Employees eligible for rule assignment: same tenant and selected plan only.

    Query:
      plan_id (required)
      q (optional search: name, employee_id, email)
      page / page_size (optional pagination; default page_size=100, max=500)
      ids_only=1 (return just matching profile ids for Select All)
    """
    _require_admin(request)
    org = getattr(request, "organization", None)
    plan_id = request.query_params.get("plan_id")
    if not plan_id:
        raise ValidationError({"plan_id": "plan_id is required."})

    from .models import CompensationPlan
    from .rule_assignments import serialize_eligible_employee

    plan = get_object_or_404(
        filter_queryset_by_organization(CompensationPlan.objects.all(), org),
        pk=plan_id,
    )
    search = request.query_params.get("q") or ""
    qs = employees_queryset_for_plan(plan.id, organization=org, search=search)

    if str(request.query_params.get("ids_only", "")).lower() in ("1", "true", "yes"):
        return Response({"count": qs.count(), "ids": list(qs.values_list("id", flat=True))})

    try:
        page = max(1, int(request.query_params.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get("page_size") or 100)
    except (TypeError, ValueError):
        page_size = 100
    page_size = max(1, min(page_size, 500))

    total = qs.count()
    start = (page - 1) * page_size
    rows = list(qs[start : start + page_size])
    return Response(
        {
            "count": total,
            "page": page,
            "page_size": page_size,
            "has_more": start + len(rows) < total,
            "results": [serialize_eligible_employee(row) for row in rows],
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_rule_invalid_assignments(request):
    """Report rule assignments that violate plan/tenant constraints."""
    _require_admin(request)
    org = getattr(request, "organization", None)
    invalid = find_invalid_assignments(organization=org)
    return Response({"count": len(invalid), "assignments": invalid})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_commission_rules(request, pk):
    """
    Commission rules explicitly assigned to one employee (tenant-scoped).

    GET /api/user-setup/{id}/commission-rules/
    GET /api/employees/{id}/commission-rules/
    """
    _require_admin(request)
    org = getattr(request, "organization", None)
    profile = get_object_or_404(
        filter_queryset_by_organization(UserProfile.objects.all(), org),
        pk=pk,
    )
    from .compensation_overrides import assigned_rules_for_employee_display

    rules = assigned_rules_for_employee_display(profile, organization=org)
    return Response({"count": len(rules), "results": rules})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_rule_choices(request):
    """Dropdown metadata for the Commission Rules UI."""
    _require_admin(request)
    return Response(
        {
            "rule_types": _choice_list(CommissionRule.RULE_TYPE_CHOICES),
            "scopes": [
                {
                    "value": value,
                    "label": label,
                    "default_priority": CommissionRule.DEFAULT_SCOPE_PRIORITY[value],
                }
                for value, label in CommissionRule.SCOPE_CHOICES
            ],
            "condition_logics": _choice_list(CommissionRule.LOGIC_CHOICES),
            "condition_fields": _choice_list(CommissionRuleCondition.FIELD_CHOICES),
            "operators": _choice_list(CommissionRuleCondition.OPERATOR_CHOICES),
            "classifications": _choice_list(CommissionRuleResult.CLASSIFICATION_CHOICES),
            "rate_types": [
                {"value": "override_tier_pct", "label": "Override tier %"},
                {"value": "add_bonus", "label": "Add bonus"},
                {"value": "percentage", "label": "Override tier % (legacy)"},
                {"value": "flat_amount", "label": "Flat amount"},
                {"value": "multiplier", "label": "Multiplier"},
                {"value": "override", "label": "Override amount"},
            ],
            "value_units": _choice_list(CommissionRuleResult.VALUE_UNIT_CHOICES),
            "quota_periods": _choice_list(CommissionRuleResult.QUOTA_PERIOD_CHOICES),
            "hold_periods": _choice_list(CommissionRuleResult.HOLD_PERIOD_CHOICES),
            "currencies": currency_choices_for_api(),
            "earning_groups": _choice_list(CommissionRuleResult.EARNING_GROUP_CHOICES),
        }
    )
