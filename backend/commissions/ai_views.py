"""API endpoints for production AI features."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .ai_features import create_ai_compensation_plan, dashboard_insights
from .ai_service import AIServiceError, ai_runtime_status, feature_enabled
from .permissions import require_admin, user_can_view_finance_data, user_is_manager


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_status(request):
    return Response(
        {
            "ai": ai_runtime_status(),
            "plan_builder_enabled": feature_enabled("AI_PLAN_BUILDER_ENABLED", False),
            "dashboard_insights_enabled": feature_enabled(
                "AI_DASHBOARD_INSIGHTS_ENABLED",
                False,
            ),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def ai_compensation_plan_builder(request):
    require_admin(request)
    if not feature_enabled("AI_PLAN_BUILDER_ENABLED", False):
        return Response(
            {"error": "AI plan builder is disabled."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    prompt = str(request.data.get("prompt") or "").strip()
    if len(prompt) < 12:
        return Response(
            {"error": "Describe the plan you want to build in at least 12 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        return Response(create_ai_compensation_plan(request), status=status.HTTP_201_CREATED)
    except ValidationError as exc:
        return Response({"error": "AI plan failed validation.", "details": exc.detail}, status=400)
    except AIServiceError as exc:
        return Response({"error": str(exc), "ai": ai_runtime_status()}, status=503)


ai_compensation_plan_builder.throttle_scope = "ai"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def ai_dashboard_insights(request):
    if not (user_can_view_finance_data(request) or user_is_manager(request)):
        raise PermissionDenied("Only administrators, finance, or managers can access AI insights")
    if not feature_enabled("AI_DASHBOARD_INSIGHTS_ENABLED", False):
        return Response(
            {"error": "AI dashboard insights are disabled."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    try:
        return Response(dashboard_insights(request))
    except AIServiceError as exc:
        return Response({"error": str(exc), "ai": ai_runtime_status()}, status=503)


ai_dashboard_insights.throttle_scope = "ai"
