from .currencies import currency_choices_for_api

from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    CommissionPlanVersion,
    CommissionRule,
    CommissionRuleCondition,
    CommissionRuleResult,
)
from .permissions import user_is_admin
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


class CommissionRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = CommissionRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _require_admin(self.request)
        qs = CommissionRule.objects.select_related(
            "compensation_plan", "plan_version"
        ).prefetch_related("conditions", "results")
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
        qs = CommissionRule.objects.select_related("plan_version").prefetch_related(
            "conditions", "results"
        )
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_update(self, serializer):
        _assert_version_editable(serializer.instance.plan_version)
        serializer.save()

    def perform_destroy(self, instance):
        _assert_version_editable(instance.plan_version)
        instance.delete()


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
