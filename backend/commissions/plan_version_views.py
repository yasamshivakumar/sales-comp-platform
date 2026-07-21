"""API views for Commission Plan Version lifecycle.

Endpoints (nested under a compensation plan):
  GET    /api/compensation-plans/<id>/versions/
  POST   /api/compensation-plans/<id>/versions/<vid>/clone/
  POST   /api/compensation-plans/<id>/versions/<vid>/publish/
  POST   /api/compensation-plans/<id>/versions/<vid>/archive/
  GET    /api/compensation-plans/<id>/versions/compare/?left=<id>&right=<id>
  GET/PATCH/DELETE  /api/compensation-plans/<id>/versions/<vid>/
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .audit import record_audit
from .models import CommissionPlanVersion, CompensationPlan
from .permissions import require_admin
from .plan_versions import (
    PlanVersionError,
    archive_version,
    clone_version,
    compare_versions,
    delete_version,
    publish_version,
)
from .serializers import CommissionPlanVersionSerializer
from .tenants import filter_queryset_by_organization


def _plan_for_request(request, plan_id):
    qs = filter_queryset_by_organization(
        CompensationPlan.objects.all(),
        getattr(request, "organization", None),
    )
    try:
        return qs.get(pk=plan_id)
    except CompensationPlan.DoesNotExist as exc:
        raise NotFound("Compensation plan not found.") from exc


def _version_for_plan(plan, version_id):
    try:
        return plan.versions.get(pk=version_id)
    except CommissionPlanVersion.DoesNotExist as exc:
        raise NotFound("Plan version not found.") from exc


def _version_queryset(plan):
    return (
        plan.versions.select_related(
            "published_by",
            "created_from_version",
            "territory",
            "compensation_plan",
        )
        .prefetch_related(
            "sc_rate_tables",
            "sc_flat_rate_tables",
            "sc_lookup_tables",
            "commission_rules",
            "commission_rules__conditions",
            "commission_rules__results",
            "quotas",
        )
        .order_by("-version_number")
    )


class PlanVersionListView(generics.ListAPIView):
    """GET /api/compensation-plans/<plan_id>/versions/ — version history."""

    serializer_class = CommissionPlanVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        require_admin(self.request)
        plan = _plan_for_request(self.request, self.kwargs["plan_id"])
        return _version_queryset(plan)


class PlanVersionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE a single plan version."""

    serializer_class = CommissionPlanVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        require_admin(self.request)
        plan = _plan_for_request(self.request, self.kwargs["plan_id"])
        return _version_for_plan(plan, self.kwargs["version_id"])

    def perform_destroy(self, instance):
        try:
            delete_version(instance)
        except PlanVersionError as exc:
            raise ValidationError(str(exc)) from exc
        record_audit(
            self.request,
            "plan_version.delete",
            detail={
                "plan_id": instance.compensation_plan_id,
                "version_number": instance.version_number,
            },
            plan_version=None,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def clone_plan_version(request, plan_id, version_id):
    require_admin(request)
    plan = _plan_for_request(request, plan_id)
    source = _version_for_plan(plan, version_id)
    try:
        draft = clone_version(
            source,
            user=request.user,
            description=request.data.get("description", ""),
        )
    except PlanVersionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    record_audit(
        request,
        "plan_version.clone",
        detail={
            "plan_id": plan.id,
            "source_version": source.version_number,
            "new_version": draft.version_number,
        },
        plan_version=draft,
    )
    return Response(
        CommissionPlanVersionSerializer(draft).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_plan_version(request, plan_id, version_id):
    require_admin(request)
    plan = _plan_for_request(request, plan_id)
    version = _version_for_plan(plan, version_id)

    # Allow optional effective-date updates before publishing.
    effective_from = request.data.get("effective_from")
    effective_to = request.data.get("effective_to", "__omit__")
    description = request.data.get("description")
    update_fields = []
    if effective_from:
        version.effective_from = effective_from
        update_fields.append("effective_from")
    if effective_to != "__omit__":
        version.effective_to = effective_to or None
        update_fields.append("effective_to")
    if description is not None:
        version.description = description
        update_fields.append("description")
    if update_fields:
        version.save(update_fields=update_fields + ["updated_at"])

    try:
        version = publish_version(version, user=request.user, strict=True)
    except PlanVersionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    superseded = getattr(version, "superseded_versions", [])
    record_audit(
        request,
        "plan_version.publish",
        detail={
            "plan_id": plan.id,
            "version_number": version.version_number,
            "effective_from": str(version.effective_from),
            "effective_to": str(version.effective_to) if version.effective_to else None,
            "superseded": superseded,
        },
        plan_version=version,
    )
    data = CommissionPlanVersionSerializer(version).data
    data["superseded_versions"] = superseded
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def archive_plan_version(request, plan_id, version_id):
    require_admin(request)
    plan = _plan_for_request(request, plan_id)
    version = _version_for_plan(plan, version_id)
    try:
        version = archive_version(version, user=request.user)
    except PlanVersionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    record_audit(
        request,
        "plan_version.archive",
        detail={"plan_id": plan.id, "version_number": version.version_number},
        plan_version=version,
    )
    return Response(CommissionPlanVersionSerializer(version).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def compare_plan_versions(request, plan_id):
    require_admin(request)
    plan = _plan_for_request(request, plan_id)
    left_id = request.query_params.get("left")
    right_id = request.query_params.get("right")
    if not left_id or not right_id:
        raise ValidationError("Query params 'left' and 'right' (version ids) are required.")

    left = _version_for_plan(plan, left_id)
    right = _version_for_plan(plan, right_id)
    return Response(compare_versions(left, right))
