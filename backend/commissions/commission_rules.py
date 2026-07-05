"""Commission rule engine: conditions → results (Xactly-style)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import CommissionRule, CommissionRuleResult

HOLD_DAYS = {
    CommissionRuleResult.HOLD_PERIOD_CHOICES[1][0]: 30,
    CommissionRuleResult.HOLD_PERIOD_CHOICES[2][0]: 60,
    CommissionRuleResult.HOLD_PERIOD_CHOICES[3][0]: 90,
}


def _decimal(value, default=Decimal("0")):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def build_rule_context(order, user_profile, plan=None):
    territory = getattr(order, "territory", None)
    order_business_group = getattr(order, "business_group", None) or ""
    profile_business_group = (
        getattr(user_profile, "business_group", None) if user_profile else ""
    ) or ""
    order_position = getattr(order, "position_name", None) or ""
    profile_position = (
        getattr(user_profile, "position_name", None) if user_profile else ""
    ) or ""
    return {
        "region": getattr(order, "region", None) or "",
        "product_name": getattr(order, "product_name", None) or "",
        "service_name": getattr(order, "service_name", None) or "",
        "distribution": getattr(order, "distribution", None) or "",
        "customer_segment": getattr(order, "customer_segment", None) or "",
        "business_group": order_business_group or profile_business_group,
        "order_status": getattr(order, "order_status", None) or "",
        "currency": getattr(order, "currency", None) or "",
        "position_name": order_position or profile_position,
        "employee_id": getattr(order, "employee_id", None) or "",
        "sales_amount": getattr(order, "sales_amount", None) or Decimal("0"),
        "territory_code": territory.code if territory else "",
        "role": getattr(user_profile, "role", None) if user_profile else "",
        "plan_basis": getattr(plan, "plan_basis", None) if plan else "",
    }


def _context_value(context, field):
    if field == "sales_amount":
        return _decimal(context.get("sales_amount"))
    return str(context.get(field, "") or "").strip()


def evaluate_condition(condition, context):
    if not condition.is_active:
        return True

    actual = _context_value(context, condition.field)
    op = condition.operator
    expected = (condition.value or "").strip()

    if op == "empty":
        return actual == "" or actual == "0"
    if op == "not_empty":
        return actual not in ("", "0")

    if condition.field == "sales_amount":
        actual_num = _decimal(actual)
        expected_num = _decimal(expected)
        if op == "eq":
            return actual_num == expected_num
        if op == "neq":
            return actual_num != expected_num
        if op == "gt":
            return actual_num > expected_num
        if op == "gte":
            return actual_num >= expected_num
        if op == "lt":
            return actual_num < expected_num
        if op == "lte":
            return actual_num <= expected_num
        return False

    actual_lower = actual.lower()
    if op == "eq":
        return actual_lower == expected.lower()
    if op == "neq":
        return actual_lower != expected.lower()
    if op == "contains":
        return expected.lower() in actual_lower
    if op == "in":
        options = [part.strip().lower() for part in expected.split(",") if part.strip()]
        return actual_lower in options
    return False


def evaluate_rule_conditions(rule, context):
    conditions = rule.conditions.filter(is_active=True).order_by("sequence", "id")
    if not conditions.exists():
        return True
    return all(evaluate_condition(condition, context) for condition in conditions)


def rule_is_effective(rule, order_date):
    if not rule.is_active or not order_date:
        return rule.is_active

    for start, end in (
        (rule.effective_start_date, rule.effective_end_date),
        (rule.active_start_date, rule.active_end_date),
    ):
        if start and order_date < start:
            return False
        if end and order_date > end:
            return False
    return True


def _apply_caps(amount, result):
    if result.minimum_value is not None and amount < result.minimum_value:
        amount = result.minimum_value
    if result.maximum_value is not None and amount > result.maximum_value:
        amount = result.maximum_value
    return amount


def _apply_result(result, rule, base_amount, credit_amount, sales_amount):
    amount = base_amount
    credit = credit_amount
    rate = _decimal(result.rate_value)

    rate_type = result.result_rate_type
    if rate_type in ("percentage", "override_tier_pct"):
        amount = sales_amount * rate / Decimal("100")
    elif rate_type == "flat_amount":
        amount = base_amount * rate
    elif rate_type == "override":
        amount = rate
    elif rate_type == "add_bonus":
        amount = base_amount + rate

    if rule.rule_type == CommissionRule.RULE_TYPE_CREDIT_AMOUNT:
        credit = rate if rate_type == "flat_amount" else sales_amount
    elif rule.rule_type == CommissionRule.RULE_TYPE_CREDIT_PERCENT:
        credit = sales_amount * rate / Decimal("100")

    amount = _apply_caps(amount, result)

    hold_until = None
    if result.hold_period and result.hold_period != "none":
        days = HOLD_DAYS.get(result.hold_period)
        if days:
            hold_until = timezone.now().date() + timedelta(days=days)

    metadata = {
        "result_classification": result.result_classification,
        "earning_group": result.earning_group,
        "hold_until": hold_until,
        "reason_code": result.reason_code,
        "rule_result_name": result.result_name,
        "value_unit_type": result.value_unit_type,
        "quota_enabled": result.quota_enabled,
        "quota_period": result.quota_period,
    }
    return amount, credit, metadata


def apply_commission_rules(plan, order, user_profile, base_amount):
    """
    Evaluate plan rules after SCRateTable base calculation.

    Returns (final_amount, credit_amount, matched_rule, metadata).
    """
    sales_amount = _decimal(getattr(order, "sales_amount", 0))
    amount = _decimal(base_amount)
    credit = sales_amount
    matched_rule = None
    metadata = {}

    if not plan:
        return amount, credit, matched_rule, metadata

    context = build_rule_context(order, user_profile, plan)
    rules = (
        CommissionRule.objects.filter(compensation_plan=plan, is_active=True)
        .prefetch_related("conditions", "results")
        .order_by("sequence", "id")
    )

    for rule in rules:
        if not rule_is_effective(rule, getattr(order, "order_date", None)):
            continue
        if not evaluate_rule_conditions(rule, context):
            continue

        matched_rule = rule
        for result in rule.results.filter(is_active=True).order_by("sequence", "id"):
            amount, credit, metadata = _apply_result(
                result, rule, amount, credit, sales_amount
            )

        mult = _decimal(rule.multiplier, Decimal("1"))
        if mult and mult != Decimal("1"):
            amount = amount * mult

        if rule.stop_on_match:
            break

    return amount, credit, matched_rule, metadata


def plan_passes_rule_conditions(plan, order, user_profile):
    """Optional gate: plan must satisfy its own rule conditions if any exist."""
    rules = CommissionRule.objects.filter(
        compensation_plan=plan,
        is_active=True,
        conditions__is_active=True,
    ).distinct()
    if not rules.exists():
        return True

    context = build_rule_context(order, user_profile, plan)
    for rule in rules:
        if not rule_is_effective(rule, getattr(order, "order_date", None)):
            continue
        if evaluate_rule_conditions(rule, context):
            return True
    return False
