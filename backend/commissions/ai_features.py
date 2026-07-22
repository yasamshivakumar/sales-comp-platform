"""Production AI features: plan builder and dashboard insights."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Sum
from django.utils.dateparse import parse_date
from .ai_service import call_json_ai
from .audit import record_audit
from .business_groups import (
    apply_business_group_to_commissions,
    apply_business_group_to_orders,
    currency_for_business_group,
    normalize_business_group,
)
from .currencies import active_currency_totals, normalize_currency
from .models import Commission, CompensationPlan, Order, UserProfile
from .serializers import CompensationPlanSerializer, CommissionRuleSerializer
from .tenants import filter_queryset_by_organization
from .enterprise_views import commission_date_q, with_commission_currency


PLAN_SCHEMA_HINT = """
{
  "plan": {
    "plan_name": "string",
    "description": "string",
    "status": "Active",
    "pay_period_type": "Monthly",
    "plan_basis": "Role",
    "effective_start_date": "YYYY-MM-DD",
    "effective_end_date": "YYYY-MM-DD or null",
    "commission_table_type": "RATE|HIGHEST|MARGINAL|FLAT|LOOKUP",
    "role": "string",
    "position_name": "string or null",
    "business_group": "India|USA|Australia|Europe"
  },
  "sc_rate_tables": [
    {"tier_name":"string","from_amount":"0","to_amount":"100000 or null","commission_rate":"5","bonus_amount":"0","sequence":1,"is_active":true}
  ],
  "sc_flat_rate_tables": [
    {"minimum_sales_threshold":"0","flat_rate":"3","bonus_amount":"0","is_active":true}
  ],
  "sc_lookup_tables": [],
  "commission_rules": [
    {
      "name":"string",
      "description":"string",
      "rule_type":"commission_rate",
      "multiplier":"1",
      "sequence":1,
      "is_active":true,
      "stop_on_match":false,
      "conditions": [{"field":"business_group","operator":"eq","value":"USA","sequence":1,"is_active":true}],
      "results": [{"result_name":"Result","result_rate_type":"add_bonus","rate_value":"500","result_classification":"bonus","earning_group":"bonus","value_unit_type":"currency","sequence":1,"is_active":true}]
    }
  ],
  "rationale": ["short reason"],
  "warnings": ["short warning"]
}
"""


PLAN_SYSTEM_PROMPT = """You are Incentra's senior compensation architect.
Design production-safe sales compensation plans. Return only JSON matching the schema.
Use conservative defaults. Prefer RATE plans with clear non-overlapping tiers unless the user asks for flat or lookup.
Never invent unsupported fields. Use only supported business groups and currencies.
Generated records will be created automatically after backend validation."""


INSIGHTS_SCHEMA_HINT = """
{
  "executive_summary": ["short insight"],
  "risks": ["short risk"],
  "opportunities": ["short opportunity"],
  "anomalies": ["short anomaly"],
  "recommended_actions": ["short action"],
  "questions_to_investigate": ["short question"]
}
"""


INSIGHTS_SYSTEM_PROMPT = """You are Incentra's senior sales compensation analyst.
Analyze only the aggregate facts provided. Do not invent missing data.
Return concise production-ready JSON for dashboard display."""


PLAN_FIELDS = {
    "plan_name",
    "description",
    "status",
    "pay_period_type",
    "plan_basis",
    "effective_start_date",
    "effective_end_date",
    "commission_table_type",
    "position_name",
    "role",
    "business_group",
    "title",
}
RATE_FIELDS = {
    "tier_name",
    "from_amount",
    "to_amount",
    "commission_rate",
    "bonus_amount",
    "sequence",
    "is_active",
}
FLAT_FIELDS = {"minimum_sales_threshold", "flat_rate", "bonus_amount", "is_active"}
LOOKUP_FIELDS = {
    "tier_name",
    "product_name",
    "service_name",
    "distribution",
    "from_amount",
    "to_amount",
    "commission_rate",
    "bonus_amount",
    "sequence",
    "is_active",
}
RULE_FIELDS = {
    "name",
    "description",
    "rule_type",
    "multiplier",
    "tags",
    "version_label",
    "effective_start_date",
    "effective_end_date",
    "active_start_date",
    "active_end_date",
    "sequence",
    "is_active",
    "stop_on_match",
    "conditions",
    "results",
}
CONDITION_FIELDS = {"field", "operator", "value", "sequence", "is_active"}
RESULT_FIELDS = {
    "result_name",
    "hold_period",
    "result_classification",
    "quota_enabled",
    "quota_period",
    "result_rate_type",
    "rate_value",
    "minimum_value",
    "maximum_value",
    "earning_group",
    "value_unit_type",
    "reason_code",
    "sequence",
    "is_active",
}


def _pick(row, fields):
    return {key: value for key, value in (row or {}).items() if key in fields}


def _clean_bool(value, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _clean_decimal(value, default="0"):
    try:
        return str(Decimal(str(value if value not in (None, "") else default)))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _safe_list(value):
    return value if isinstance(value, list) else []


def _normalize_plan_payload(ai_data, request_data, org):
    raw_plan = _pick(ai_data.get("plan") or {}, PLAN_FIELDS)
    business_group = normalize_business_group(
        request_data.get("business_group") or raw_plan.get("business_group") or "India"
    )
    role = str(request_data.get("role") or raw_plan.get("role") or "Sales Rep").strip()
    table_type = str(
        request_data.get("commission_table_type")
        or raw_plan.get("commission_table_type")
        or "RATE"
    ).upper()
    if table_type not in {"RATE", "HIGHEST", "MARGINAL", "FLAT", "LOOKUP"}:
        table_type = "RATE"
    plan = {
        **raw_plan,
        "status": raw_plan.get("status") or "Active",
        "pay_period_type": raw_plan.get("pay_period_type") or "Monthly",
        "plan_basis": raw_plan.get("plan_basis") or "Role",
        "commission_table_type": table_type,
        "role": role,
        "business_group": business_group,
    }
    if request_data.get("effective_start_date"):
        plan["effective_start_date"] = request_data.get("effective_start_date")
    if request_data.get("effective_end_date"):
        plan["effective_end_date"] = request_data.get("effective_end_date")
    if request_data.get("position_name"):
        plan["position_name"] = request_data.get("position_name")
    if not plan.get("plan_name"):
        plan["plan_name"] = f"AI {business_group} {role} Plan"
    if org and CompensationPlan.objects.filter(
        organization=org,
        plan_name__iexact=plan["plan_name"],
    ).exists():
        plan["plan_name"] = f"{plan['plan_name']} AI"

    rate_rows = []
    for index, row in enumerate(_safe_list(ai_data.get("sc_rate_tables")), start=1):
        clean = _pick(row, RATE_FIELDS)
        clean["from_amount"] = _clean_decimal(clean.get("from_amount"), "0")
        clean["to_amount"] = None if clean.get("to_amount") in ("", None) else _clean_decimal(clean.get("to_amount"))
        clean["commission_rate"] = _clean_decimal(clean.get("commission_rate"), "0")
        clean["bonus_amount"] = _clean_decimal(clean.get("bonus_amount"), "0")
        clean["sequence"] = int(clean.get("sequence") or index)
        clean["is_active"] = _clean_bool(clean.get("is_active"), True)
        rate_rows.append(clean)

    flat_rows = []
    for row in _safe_list(ai_data.get("sc_flat_rate_tables")):
        clean = _pick(row, FLAT_FIELDS)
        clean["minimum_sales_threshold"] = _clean_decimal(clean.get("minimum_sales_threshold"), "0")
        clean["flat_rate"] = _clean_decimal(clean.get("flat_rate"), "0")
        clean["bonus_amount"] = _clean_decimal(clean.get("bonus_amount"), "0")
        clean["is_active"] = _clean_bool(clean.get("is_active"), True)
        flat_rows.append(clean)

    lookup_rows = []
    for index, row in enumerate(_safe_list(ai_data.get("sc_lookup_tables")), start=1):
        clean = _pick(row, LOOKUP_FIELDS)
        clean["from_amount"] = _clean_decimal(clean.get("from_amount"), "0")
        clean["to_amount"] = None if clean.get("to_amount") in ("", None) else _clean_decimal(clean.get("to_amount"))
        clean["commission_rate"] = _clean_decimal(clean.get("commission_rate"), "0")
        clean["bonus_amount"] = _clean_decimal(clean.get("bonus_amount"), "0")
        clean["sequence"] = int(clean.get("sequence") or index)
        clean["is_active"] = _clean_bool(clean.get("is_active"), True)
        lookup_rows.append(clean)

    if table_type == "RATE" and not rate_rows:
        rate_rows = [
            {
                "tier_name": "Base tier",
                "from_amount": "0",
                "to_amount": None,
                "commission_rate": "5",
                "bonus_amount": "0",
                "sequence": 1,
                "is_active": True,
            }
        ]
    if table_type == "FLAT" and not flat_rows:
        flat_rows = [{"minimum_sales_threshold": "0", "flat_rate": "3", "bonus_amount": "0", "is_active": True}]

    payload = {
        **plan,
        "sc_rate_tables": rate_rows if table_type == "RATE" else [],
        "sc_flat_rate_tables": flat_rows if table_type == "FLAT" else [],
        "sc_lookup_tables": lookup_rows if table_type == "LOOKUP" else [],
    }
    rules = []
    for index, row in enumerate(_safe_list(ai_data.get("commission_rules")), start=1):
        rule = _pick(row, RULE_FIELDS)
        rule["name"] = str(rule.get("name") or f"AI Rule {index}")[:255]
        rule["rule_type"] = rule.get("rule_type") or "commission_rate"
        rule["multiplier"] = _clean_decimal(rule.get("multiplier"), "1")
        rule["sequence"] = int(rule.get("sequence") or index)
        rule["is_active"] = _clean_bool(rule.get("is_active"), True)
        rule["stop_on_match"] = _clean_bool(rule.get("stop_on_match"), False)
        rule["conditions"] = [_pick(item, CONDITION_FIELDS) for item in _safe_list(rule.get("conditions"))]
        rule["results"] = [_pick(item, RESULT_FIELDS) for item in _safe_list(rule.get("results"))]
        for result_index, result in enumerate(rule["results"], start=1):
            result["result_name"] = str(result.get("result_name") or "AI result")[:255]
            result["result_rate_type"] = result.get("result_rate_type") or "add_bonus"
            result["rate_value"] = _clean_decimal(result.get("rate_value"), "0")
            result["sequence"] = int(result.get("sequence") or result_index)
            result["is_active"] = _clean_bool(result.get("is_active"), True)
        rules.append(rule)
    return payload, rules


def _sample_simulation(plan_payload, request_data):
    samples = _safe_list(request_data.get("sample_orders"))[:5]
    if not samples:
        samples = [{"sales_amount": "10000"}, {"sales_amount": "50000"}, {"sales_amount": "100000"}]
    rows = []
    table_type = plan_payload.get("commission_table_type")
    for sample in samples:
        sales = Decimal(_clean_decimal(sample.get("sales_amount"), "0"))
        estimate = Decimal("0")
        if table_type in ("RATE", "HIGHEST"):
            for tier in plan_payload.get("sc_rate_tables", []):
                start = Decimal(_clean_decimal(tier.get("from_amount"), "0"))
                end = tier.get("to_amount")
                if sales >= start and (end in (None, "") or sales <= Decimal(str(end))):
                    estimate = sales * Decimal(str(tier["commission_rate"])) / Decimal("100")
                    estimate += Decimal(str(tier.get("bonus_amount") or "0"))
                    break
        elif table_type == "MARGINAL":
            # Fill model on a single order from an empty fill level: top up the
            # first band at its rate, then the rest of the order at the next
            # band's rate (remainder is not capped at that band's width).
            tiers = sorted(
                plan_payload.get("sc_rate_tables", []),
                key=lambda t: Decimal(_clean_decimal(t.get("from_amount"), "0")),
            )
            if tiers and sales > 0:
                first = tiers[0]
                first_rate = Decimal(str(first.get("commission_rate") or "0"))
                first_end = first.get("to_amount")
                open_top = first_end in (None, "") or len(tiers) == 1
                room = sales if open_top else Decimal(str(first_end))
                if sales <= room:
                    estimate = sales * first_rate / Decimal("100")
                    estimate += Decimal(str(first.get("bonus_amount") or "0"))
                else:
                    nxt = tiers[1]
                    nxt_rate = Decimal(str(nxt.get("commission_rate") or "0"))
                    remainder = sales - room
                    estimate = room * first_rate / Decimal("100")
                    estimate += remainder * nxt_rate / Decimal("100")
                    estimate += Decimal(str(nxt.get("bonus_amount") or "0"))
        elif table_type == "FLAT":
            flat = (plan_payload.get("sc_flat_rate_tables") or [{}])[0]
            estimate = sales * Decimal(str(flat.get("flat_rate") or "0")) / Decimal("100")
            estimate += Decimal(str(flat.get("bonus_amount") or "0"))
        rows.append({"sales_amount": float(sales), "estimated_commission": float(estimate)})
    return rows


def create_ai_compensation_plan(request):
    org = getattr(request, "organization", None)
    user_payload = {
        "request": {
            "prompt": str(request.data.get("prompt") or "")[:4000],
            "role": request.data.get("role"),
            "business_group": request.data.get("business_group"),
            "currency": normalize_currency(
                request.data.get("currency")
                or currency_for_business_group(request.data.get("business_group"), None)
            ),
            "effective_start_date": request.data.get("effective_start_date"),
            "effective_end_date": request.data.get("effective_end_date"),
            "commission_table_type": request.data.get("commission_table_type"),
            "position_name": request.data.get("position_name"),
            "sample_orders": _safe_list(request.data.get("sample_orders"))[:5],
        },
        "constraints": {
            "supported_table_types": ["RATE", "FLAT", "LOOKUP"],
            "supported_business_groups": ["India", "USA", "Australia", "Europe"],
            "auto_create": True,
        },
    }
    ai_data, runtime = call_json_ai(
        system_prompt=PLAN_SYSTEM_PROMPT,
        user_payload=user_payload,
        schema_hint=PLAN_SCHEMA_HINT,
        temperature=0.15,
        max_tokens=2200,
    )
    plan_payload, rules = _normalize_plan_payload(ai_data, request.data, org)
    simulation = _sample_simulation(plan_payload, request.data)

    with transaction.atomic():
        serializer = CompensationPlanSerializer(
            data=plan_payload,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        plan = serializer.save(organization=org)
        created_rules = []
        for rule_payload in rules:
            rule_payload["compensation_plan"] = plan.id
            rule_serializer = CommissionRuleSerializer(
                data=rule_payload,
                context={"request": request},
            )
            rule_serializer.is_valid(raise_exception=True)
            rule = rule_serializer.save(organization=org, compensation_plan=plan)
            created_rules.append(rule)

    record_audit(
        request,
        "ai_compensation_plan_created",
        {
            "plan_id": plan.id,
            "rule_ids": [rule.id for rule in created_rules],
            "provider": runtime.get("provider"),
            "model": runtime.get("model"),
            "rationale": ai_data.get("rationale", [])[:5],
            "warnings": ai_data.get("warnings", [])[:5],
        },
    )
    return {
        "plan": CompensationPlanSerializer(plan).data,
        "rules_created": [rule.id for rule in created_rules],
        "simulation": simulation,
        "rationale": ai_data.get("rationale", []),
        "warnings": ai_data.get("warnings", []),
        "ai": runtime,
    }


def dashboard_insights(request):
    org = getattr(request, "organization", None)
    start_date = parse_date(request.query_params.get("start_date") or "")
    end_date = parse_date(request.query_params.get("end_date") or "")
    business_group = request.query_params.get("business_group")

    commissions = filter_queryset_by_organization(Commission.objects.all(), org)
    commissions = commissions.filter(commission_date_q(start_date, end_date))
    commissions = apply_business_group_to_commissions(commissions, business_group, organization=org)
    commissions = with_commission_currency(commissions)

    orders = filter_queryset_by_organization(Order.objects.all(), org)
    if start_date and end_date:
        orders = orders.filter(order_date__range=[start_date, end_date])
    orders = apply_business_group_to_orders(orders, business_group, organization=org)

    profiles = filter_queryset_by_organization(UserProfile.objects.all(), org)
    if business_group and business_group != "all":
        profiles = profiles.filter(business_group__iexact=normalize_business_group(business_group))

    commission_totals = [
        {
            "currency": normalize_currency(row["report_currency"]),
            "total": float(row["total"] or 0),
            "count": row["count"],
        }
        for row in commissions.values("report_currency").annotate(
            total=Sum("commission_amount"),
            count=Count("id"),
        )
    ]
    sales_total = orders.aggregate(total=Sum("sales_amount"), count=Count("id"))
    quota_profiles = profiles.exclude(personal_target=0).count()
    facts = {
        "date_range": {"start_date": str(start_date or ""), "end_date": str(end_date or "")},
        "business_group": business_group or "all",
        "commission_totals": commission_totals,
        "sales": {
            "total": float(sales_total["total"] or 0),
            "order_count": sales_total["count"],
        },
        "active_reps": commissions.values("employee_id").distinct().count(),
        "quota_profiles": quota_profiles,
        "totals_by_currency": active_currency_totals(commission_totals),
    }
    ai_data, runtime = call_json_ai(
        system_prompt=INSIGHTS_SYSTEM_PROMPT,
        user_payload=facts,
        schema_hint=INSIGHTS_SCHEMA_HINT,
        temperature=0.25,
        max_tokens=1200,
    )
    response = {
        "executive_summary": _safe_list(ai_data.get("executive_summary"))[:5],
        "risks": _safe_list(ai_data.get("risks"))[:5],
        "opportunities": _safe_list(ai_data.get("opportunities"))[:5],
        "anomalies": _safe_list(ai_data.get("anomalies"))[:5],
        "recommended_actions": _safe_list(ai_data.get("recommended_actions"))[:5],
        "questions_to_investigate": _safe_list(ai_data.get("questions_to_investigate"))[:5],
        "facts": facts,
        "ai": runtime,
    }
    record_audit(
        request,
        "ai_dashboard_insights_generated",
        {"provider": runtime.get("provider"), "model": runtime.get("model"), "business_group": facts["business_group"]},
    )
    return response
