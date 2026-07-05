"""API for commission explanation, Q&A, and what-if simulator."""

from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .commission_explanation import (
    answer_commission_question,
    build_commission_explanation,
    simulate_what_if,
)
from .commission_ai import ai_setup_status
from .enterprise_views import _commissions_for_user


def _commission_for_user(request, commission_id):
    qs = _commissions_for_user(request)
    return get_object_or_404(qs, pk=commission_id)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def commission_explanation_view(request, commission_id):
    """Step-by-step breakdown for one commission."""
    commission = _commission_for_user(request, commission_id)
    data = build_commission_explanation(commission)
    if data.get("error"):
        return Response(data, status=400)
    data["ai"] = ai_setup_status()
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def commission_explanation_ask_view(request, commission_id):
    """Plain-English answer to a natural-language question about a commission."""
    commission = _commission_for_user(request, commission_id)
    question = request.data.get("question", "")
    return Response(answer_commission_question(commission, question, request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def commission_what_if_view(request):
    """
    What-if: extra sales in a date range → projected commission.

    Body: { extra_sales, start_date, end_date }
    """
    raw = request.data.get("extra_sales")
    try:
        extra_sales = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return Response({"error": "extra_sales must be a number"}, status=400)

    start_date = request.data.get("start_date")
    end_date = request.data.get("end_date")
    if not start_date or not end_date:
        return Response(
            {"error": "start_date and end_date are required (YYYY-MM-DD)."},
            status=400,
        )

    data = simulate_what_if(request, extra_sales, start_date, end_date)
    if data.get("error"):
        return Response(data, status=400)
    return Response(data)
