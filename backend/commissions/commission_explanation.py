"""Plain-English commission breakdown, peer comparison, and what-if simulation."""

from __future__ import annotations

import re
from decimal import Decimal

from django.db.models import Q

from .commission_rules import (
    apply_commission_rules,
    build_rule_context,
    evaluate_rule_conditions,
    rule_is_effective,
    _decimal,
)
from .models import (
    Commission,
    CommissionRule,
    CompensationPlan,
    Order,
    SCRateTable,
    SCFlatRateTable,
    SCLookupTable,
    UserProfile,
)
from .plan_periods import parse_date
from .currencies import format_currency_amount, normalize_currency
from .services import (
    _calculate_amount_for_plan,
    _get_user_profile_for_order,
    find_sc_lookup_tier,
    resolve_compensation_plan,
)


def _inr(amount, currency=None) -> str:
    return format_currency_amount(amount, normalize_currency(currency))


def _pct(value) -> str:
    return f"{_decimal(value):.2f}%"


def _tier_breakdown(plan, sales_amount, order=None):
    sales_amount = _decimal(sales_amount)
    if plan.commission_table_type == "RATE":
        tier = (
            SCRateTable.objects.filter(
                compensation_plan=plan,
                is_active=True,
                from_amount__lte=sales_amount,
            )
            .filter(Q(to_amount__gte=sales_amount) | Q(to_amount__isnull=True))
            .order_by("sequence")
            .first()
        )
        if not tier:
            return None, Decimal("0"), {}
        base = sales_amount * tier.commission_rate / Decimal("100") + tier.bonus_amount
        to_label = tier.to_amount if tier.to_amount is not None else None
        return tier, base, {
            "rate_pct": tier.commission_rate,
            "tier_bonus": tier.bonus_amount,
            "tier_name": tier.tier_name or "Rate tier",
            "from_amount": tier.from_amount,
            "to_amount": to_label,
        }
    if plan.commission_table_type == "FLAT":
        flat = SCFlatRateTable.objects.filter(
            compensation_plan=plan,
            is_active=True,
            minimum_sales_threshold__lte=sales_amount,
        ).first()
        if not flat:
            return None, Decimal("0"), {}
        base = sales_amount * flat.flat_rate / Decimal("100") + flat.bonus_amount
        return flat, base, {
            "rate_pct": flat.flat_rate,
            "tier_bonus": flat.bonus_amount,
            "tier_name": "Flat rate",
            "from_amount": flat.minimum_sales_threshold,
            "to_amount": None,
        }
    if plan.commission_table_type == "LOOKUP":
        tier = find_sc_lookup_tier(plan, order, sales_amount)
        if not tier:
            return None, Decimal("0"), {}
        base = sales_amount * tier.commission_rate / Decimal("100") + tier.bonus_amount
        dims = []
        if tier.product_name:
            dims.append(f"Product: {tier.product_name}")
        if tier.service_name:
            dims.append(f"Service: {tier.service_name}")
        if tier.distribution:
            dims.append(f"Distribution: {tier.distribution}")
        dim_label = " · ".join(dims) if dims else "Any product/service/distribution"
        to_amt = tier.to_amount
        band = f"₹{tier.from_amount:,.0f} – "
        band += f"₹{to_amt:,.0f}" if to_amt is not None else "no upper limit"
        return tier, base, {
            "rate_pct": tier.commission_rate,
            "tier_bonus": tier.bonus_amount,
            "tier_name": tier.tier_name or "Lookup tier",
            "from_amount": tier.from_amount,
            "to_amount": to_amt,
            "lookup_match": dim_label,
            "lookup_band": band,
        }
    return None, Decimal("0"), {}


def _describe_rule_adjustment(rule, result, before, after, sales_amount, currency=None):
    rate_type = result.result_rate_type
    rate = _decimal(result.rate_value)
    if rate_type in ("percentage", "override_tier_pct"):
        return (
            f"Rule “{rule.name}” replaced the tier rate with {rate}% of order value "
            f"({_inr(after, currency)})."
        )
    if rate_type == "add_bonus":
        return (
            f"Rule “{rule.name}” added a bonus of {_inr(rate, currency)} "
            f"({_inr(before, currency)} → {_inr(after, currency)})."
        )
    if rate_type == "multiplier":
        return f"Rule “{rule.name}” applied a {rate}x multiplier on commission."
    if rate_type == "override":
        return f"Rule “{rule.name}” set commission to a flat {_inr(rate, currency)}."
    if rate_type == "flat_amount":
        return f"Rule “{rule.name}” adjusted commission to {_inr(after, currency)}."
    return f"Rule “{rule.name}” adjusted commission ({_inr(before, currency)} → {_inr(after, currency)})."


def _rule_steps(plan, order, user_profile, base_amount, currency=None):
    steps = []
    amount = _decimal(base_amount)
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
        before_rule = amount
        for result in rule.results.filter(is_active=True).order_by("sequence", "id"):
            before = amount
            rate_type = result.result_rate_type
            rate = _decimal(result.rate_value)
            if rate_type in ("percentage", "override_tier_pct"):
                amount = _decimal(order.sales_amount) * rate / Decimal("100")
                label = "Override tier rate"
                display = _pct(rate)
            elif rate_type == "add_bonus":
                amount = amount + rate
                label = "Commission rule bonus"
                display = _inr(rate, currency)
            elif rate_type == "multiplier":
                amount = amount * rate
                label = "Rule multiplier"
                display = f"{rate}x"
            elif rate_type in ("override", "flat_amount"):
                amount = rate if rate_type == "override" else amount
                label = "Rule flat adjustment"
                display = _inr(amount, currency)
            else:
                label = result.result_name or "Rule adjustment"
                display = _inr(amount, currency)
            steps.append(
                {
                    "key": f"rule_{rule.id}",
                    "label": label,
                    "display": display,
                    "detail": _describe_rule_adjustment(
                        rule, result, before, amount, order.sales_amount, currency
                    ),
                    "checked": True,
                    "rule_name": rule.name,
                }
            )
        mult = _decimal(rule.multiplier, Decimal("1"))
        if mult and mult != Decimal("1"):
            before = amount
            amount = amount * mult
            steps.append(
                {
                    "key": f"rule_mult_{rule.id}",
                    "label": "Rule multiplier",
                    "display": f"{mult}x",
                    "detail": f"Rule “{rule.name}” multiplied commission "
                    f"({_inr(before, currency)} → {_inr(amount, currency)}).",
                    "checked": True,
                }
            )
        if rule.stop_on_match:
            break
    return amount, steps


def _hierarchy_step(order, gross_amount, net_amount, currency=None):
    if gross_amount == net_amount:
        return None
    profile = _get_user_profile_for_order(order)
    if not profile:
        return None
    from .models import HierarchyRelationship

    rel = HierarchyRelationship.objects.filter(
        child_participant=profile, is_active=True
    ).first()
    if not rel:
        return None
    pct = _decimal(rel.split_percentage, Decimal("100"))
    return {
        "key": "hierarchy_split",
        "label": "Your share (hierarchy split)",
        "display": _pct(pct),
        "detail": (
            f"Calculated commission was {_inr(gross_amount, currency)}; "
            f"you retain {pct}% ({_inr(net_amount, currency)})."
        ),
        "checked": True,
    }


def build_commission_explanation(commission: Commission) -> dict:
    """Structured breakdown + summary for one commission row."""
    comm = (
        Commission.objects.select_related(
            "employee",
            "sale",
            "sale__order",
            "sale__order__territory",
            "compensation_plan",
            "commission_rule",
        )
        .filter(pk=commission.pk)
        .first()
    )
    if not comm or not comm.sale_id:
        return {"error": "Commission has no linked order."}

    order = comm.sale.order
    plan = comm.compensation_plan
    user_profile = _get_user_profile_for_order(order)
    sales_amount = _decimal(order.sales_amount)
    currency = normalize_currency(getattr(order, "currency", None))

    lines = [
        {
            "key": "order_value",
            "label": "Order value",
            "display": _inr(sales_amount, currency),
            "detail": f"Order {order.order_id} on {order.order_date}.",
            "checked": True,
        }
    ]

    if getattr(order, "currency", None):
        lines.append(
            {
                "key": "currency",
                "label": "Currency",
                "display": currency,
                "checked": True,
            }
        )

    if order.product_name:
        lines.append(
            {
                "key": "product",
                "label": "Product",
                "display": order.product_name,
                "checked": True,
            }
        )

    if order.service_name:
        lines.append(
            {
                "key": "service",
                "label": "Service",
                "display": order.service_name,
                "checked": True,
            }
        )

    if getattr(order, "distribution", None):
        lines.append(
            {
                "key": "distribution",
                "label": "Distribution",
                "display": order.distribution,
                "checked": True,
            }
        )

    if order.territory_id and order.territory:
        lines.append(
            {
                "key": "territory",
                "label": "Territory",
                "display": order.territory.name,
                "checked": True,
            }
        )

    base_amount = Decimal("0")
    tier_meta = {}
    if plan:
        tier, base_amount, tier_meta = _tier_breakdown(plan, sales_amount, order)
        if tier_meta:
            to_amt = tier_meta.get("to_amount")
            if plan.commission_table_type == "LOOKUP":
                band = tier_meta.get("lookup_band", "")
                match = tier_meta.get("lookup_match", "")
                detail = f"{match} · Sales band {band}."
            else:
                from .currencies import currency_meta

                symbol = currency_meta(currency)["symbol"]
                band = f"{symbol}{tier_meta['from_amount']:,.0f} – "
                band += f"{symbol}{to_amt:,.0f}" if to_amt is not None else "no upper limit"
                detail = f"{tier_meta['tier_name']} · {band}."
            lines.append(
                {
                    "key": "commission_rate",
                    "label": "Commission rate (plan tier)",
                    "display": _pct(tier_meta["rate_pct"]),
                    "detail": detail,
                    "checked": True,
                }
            )
            if tier_meta.get("tier_bonus") and tier_meta["tier_bonus"] > 0:
                lines.append(
                    {
                        "key": "tier_bonus",
                        "label": "Tier bonus",
                        "display": _inr(tier_meta["tier_bonus"], currency),
                        "checked": True,
                    }
                )
            lines.append(
                {
                    "key": "base_commission",
                    "label": "Base commission (before rules)",
                    "display": _inr(base_amount, currency),
                    "checked": True,
                }
            )
        lines.append(
            {
                "key": "plan",
                "label": "Compensation plan",
                "display": plan.plan_name,
                "checked": True,
            }
        )
    else:
        plan, _ = resolve_compensation_plan(order)
        if plan:
            base_amount = _calculate_amount_for_plan(plan, sales_amount, order=order)

    rule_steps = []
    if plan:
        _, rule_steps = _rule_steps(plan, order, user_profile, base_amount, currency)
        lines.extend(rule_steps)

    gross = base_amount
    if plan:
        gross, _, _, _ = apply_commission_rules(plan, order, user_profile, base_amount)

    net = _decimal(comm.commission_amount)
    hierarchy = _hierarchy_step(order, gross, net, currency)
    if hierarchy:
        lines.append(hierarchy)

    lines.append(
        {
            "key": "final_commission",
            "label": "Final commission (your payout)",
            "display": _inr(net, currency),
            "checked": True,
            "highlight": True,
        }
    )

    summary_parts = [
        f"You earned {_inr(net, currency)} on order {order.order_id}.",
    ]
    if tier_meta:
        summary_parts.append(
            f"The plan tier rate is {_pct(tier_meta['rate_pct'])} on {_inr(sales_amount, currency)}."
        )
    if rule_steps:
        summary_parts.append(
            f"{len(rule_steps)} commission rule adjustment(s) applied."
        )
    if hierarchy:
        summary_parts.append(
            f"After hierarchy split you receive {_inr(net, currency)}."
        )

    return {
        "commission_id": comm.id,
        "commission_earned": str(net),
        "currency": currency,
        "order_id": order.order_id,
        "order_date": str(order.order_date) if order.order_date else None,
        "employee_name": comm.employee.name,
        "lines": lines,
        "summary": " ".join(summary_parts),
    }


def _period_sales_and_commission(profile, start_date, end_date):
    qs = Commission.objects.filter(
        employee__email=profile.email,
        organization=getattr(profile, "organization", None),
        sale__order__order_date__gte=start_date,
        sale__order__order_date__lte=end_date,
    )
    total_commission = sum(_decimal(c.commission_amount) for c in qs)
    order_qs = Order.objects.filter(
        employee_id=profile.employee_id,
        organization=getattr(profile, "organization", None),
        order_date__gte=start_date,
        order_date__lte=end_date,
    )
    total_sales = sum(_decimal(o.sales_amount) for o in order_qs)
    target = _decimal(profile.personal_target)
    attainment = (
        float(total_sales / target * 100) if target > 0 else None
    )
    return {
        "total_commission": total_commission,
        "total_sales": total_sales,
        "quota_target": target,
        "quota_attainment_pct": round(attainment, 1) if attainment is not None else None,
        "order_count": order_qs.count(),
    }


def _find_peer_profile(name_query, organization_id=None):
    term = (name_query or "").strip()
    if not term:
        return None
    qs = UserProfile.objects.filter(
        Q(name__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(employee_id__iexact=term)
    )
    if organization_id:
        qs = qs.filter(organization_id=organization_id)
    return qs.first()


def _tokenize(text):
    stop = {
        "the", "and", "for", "this", "that", "what", "why", "how", "did", "was",
        "are", "my", "me", "can", "you", "any", "about", "with", "from", "have",
        "has", "get", "got", "will", "would", "should", "could", "when", "where",
        "who", "which", "much", "many", "does", "do", "not", "but", "all", "one",
    }
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [t for t in tokens if len(t) > 2 and t not in stop]


def _is_time_phrase(name):
    lower = (name or "").lower()
    time_phrases = (
        "current month",
        "last month",
        "next month",
        "this month",
        "previous month",
        "same month",
        "month commission",
        "month's commission",
        "prior month",
    )
    return any(phrase in lower for phrase in time_phrases)


def _next_month_bounds(from_date):
    from dateutil.relativedelta import relativedelta

    start = from_date.replace(day=1) + relativedelta(months=1)
    end = start + relativedelta(months=1, days=-1)
    return start, end


def _effective_commission_rate_pct(plan, order, profile, sales_amount):
    """Approximate commission as % of sales for coaching estimates."""
    sales_amount = _decimal(sales_amount)
    if sales_amount <= 0:
        return None
    if not plan:
        plan, _ = resolve_compensation_plan(order)
    if not plan:
        return None
    base = _calculate_amount_for_plan(plan, sales_amount)
    amount, _, _, _ = apply_commission_rules(plan, order, profile, base)
    if amount <= 0:
        return None
    return float(amount / sales_amount * 100)


def _answer_earn_more_guidance(commission, request, explanation):
    """
    Actionable guidance for earning more commission next period vs current period.
    """
    profile = get_request_profile(request)
    order = commission.sale.order if commission.sale_id else None
    if not profile or not order:
        return None

    start, end = _order_period_bounds(order)
    current = _period_sales_and_commission(profile, start, end)
    current_comm = current["total_commission"]
    current_sales = current["total_sales"]
    month_label = start.strftime("%B %Y")
    next_start, _ = _next_month_bounds(order.order_date)
    next_label = next_start.strftime("%B %Y")

    plan = commission.compensation_plan
    if not plan:
        plan, _ = resolve_compensation_plan(order)

    rate_pct = None
    if current_sales > 0 and current_comm > 0:
        rate_pct = float(current_comm / current_sales * 100)
    elif plan:
        sample = _decimal(order.sales_amount) or Decimal("100000")
        rate_pct = _effective_commission_rate_pct(plan, order, profile, sample)

    parts = [
        f"In {month_label} you've earned {_inr(current_comm)} in commission "
        f"from {_inr(current_sales)} in sales across {current['order_count']} order(s). ",
        f"To earn more in {next_label} than this month, here is a practical plan: ",
    ]

    tips = []
    beat_target = (current_comm * Decimal("1.05")).quantize(Decimal("0.01"))
    if current_comm <= 0:
        tips.append(
            "start closing qualified deals — you have little or no commission recorded "
            f"this month yet, so any approved sales in {next_label} will increase earnings"
        )
        if rate_pct:
            tips.append(
                f"each ₹1,00,000 in sales at your plan's ~{rate_pct:.1f}% effective rate "
                f"is roughly {_inr(Decimal('100000') * Decimal(str(rate_pct)) / Decimal('100'))} in commission"
            )
    elif rate_pct and rate_pct > 0:
        rate = Decimal(str(rate_pct)) / Decimal("100")
        sales_for_beat = (beat_target / rate).quantize(Decimal("1"))
        extra_sales = max(Decimal("0"), sales_for_beat - current_sales)
        tips.append(
            f"increase sales by about {_inr(extra_sales)} "
            f"(≈ {_inr(beat_target)} total commission at your recent ~{rate_pct:.1f}% effective rate)"
        )
        tips.append(
            f"that means roughly {max(1, int(extra_sales / Decimal('100000')))} additional "
            f"₹1L deal(s), depending on deal size and rules"
        )
    else:
        tips.append(
            "focus on higher-value orders — your commission grows with eligible sales volume"
        )

    if current["quota_target"] > 0:
        attainment = current["quota_attainment_pct"]
        if attainment is not None and attainment < 100:
            gap = current["quota_target"] - current_sales
            tips.append(
                f"close the quota gap of {_inr(gap)} "
                f"(you are at {attainment:.0f}% of {_inr(current['quota_target'])})"
            )
        elif attainment is not None and attainment >= 100:
            tips.append(
                "you hit quota this month — push volume further or target larger deals to grow commission"
            )

    lines = explanation.get("lines", [])
    if _lines_by_keys(lines, {"commission_rate"}):
        tips.append(
            "check whether higher cumulative sales unlock a better tier rate on your compensation plan"
        )
    if any(str(line.get("key", "")).startswith("rule") for line in lines):
        tips.append(
            "prioritize products, regions, or segments where active commission rules pay bonuses or higher rates"
        )

    tips.append(
        "use the What-if simulator in this panel to model extra sales before you commit to targets"
    )

    for index, tip in enumerate(tips, start=1):
        parts.append(f"{index}. {tip[0].upper()}{tip[1:]}. ")

    return {"answer": "".join(parts)}


def _wants_earn_more_advice(question):
    lower = question.lower()
    earn_signals = (
        "earn more",
        "make more",
        "get more",
        "increase commission",
        "grow commission",
        "boost commission",
        "improve commission",
        "maximize",
        "how can i earn",
        "how do i earn",
        "how to earn",
        "beat my",
        "beat this",
        "exceed",
        "surpass",
        "better than",
        "more commission",
        "more next",
        "next month",
        "following month",
        "tips to",
        "way to earn",
        "ways to earn",
    )
    topic_signals = ("commission", "earn", "payout", "incentive", "money", "sales")
    if not any(signal in lower for signal in earn_signals):
        return False
    if not any(signal in lower for signal in topic_signals):
        return False
    # Month-over-month comparison
    if "next month" in lower and ("current" in lower or "this month" in lower or "month" in lower):
        return True
    if any(signal in lower for signal in ("earn more", "make more", "get more", "increase", "boost", "grow")):
        return True
    return "how can" in lower or "how do" in lower or "how to" in lower


def _extract_peer_name(question):
    patterns = [
        r"(?:less than|more than|lower than|higher than|compared to|compare with|compare to|vs\.?|versus|difference with|against)\s+(.+?)(?:\?|\.|$)",
        r"why\s+(?:did\s+)?i\s+(?:earn|get|make|receive)\s+(?:less|more|lower|higher)\s+than\s+(.+?)(?:\?|\.|$)",
        r"(?:earn|earned)\s+(?:less|more|lower|higher)\s+than\s+(.+?)(?:\?|\.|$)",
        r"compare\s+(?:me\s+)?(?:to|with)\s+(.+?)(?:\?|\.|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question.strip(), re.I)
        if not match:
            continue
        name = match.group(1).strip().strip("'\"").rstrip("?.!")
        if name and name.lower() not in ("them", "him", "her", "you", "someone"):
            if _is_time_phrase(name):
                continue
            return name
    return None


def _match_explanation_lines(question, lines, limit=3):
    tokens = _tokenize(question)
    if not tokens:
        return []
    scored = []
    for line in lines:
        blob = " ".join(
            str(line.get(key, ""))
            for key in ("label", "display", "detail", "rule_name", "key")
        ).lower()
        score = sum(1 for token in tokens if token in blob)
        if score:
            scored.append((score, line))
    scored.sort(key=lambda item: -item[0])
    return [line for _, line in scored[:limit]]


def _lines_by_keys(lines, keys):
    key_set = set(keys)
    return [line for line in lines if line.get("key") in key_set]


def _format_lines_answer(intro, lines):
    parts = [intro]
    for line in lines:
        parts.append(line.get("detail") or f"{line['label']}: {line['display']}.")
    return " ".join(parts)


def _order_period_bounds(order):
    from calendar import monthrange

    start = order.order_date.replace(day=1)
    last_day = monthrange(order.order_date.year, order.order_date.month)[1]
    end = order.order_date.replace(day=last_day)
    return start, end


def _answer_peer_comparison(commission, question, request, peer_name=None):
    peer_name = peer_name or _extract_peer_name(question)
    if not peer_name:
        return None

    order = commission.sale.order if commission.sale_id else None
    org_id = getattr(order, "organization_id", None) if order else None
    peer = _find_peer_profile(peer_name, org_id)
    if not peer:
        return {
            "answer": (
                f"I couldn't find “{peer_name}” in User Setup. "
                "Check the spelling or use their employee ID."
            ),
        }

    profile = get_request_profile(request)
    if not profile:
        return {"answer": "Your user profile was not found."}
    if not order:
        return {"answer": "This commission is not linked to an order."}

    start, end = _order_period_bounds(order)
    yours = _period_sales_and_commission(profile, start, end)
    theirs = _period_sales_and_commission(peer, start, end)
    diff = theirs["total_commission"] - yours["total_commission"]
    peer_label = peer.name or peer.employee_id

    parts = [
        f"In {start.strftime('%B %Y')}, you earned {_inr(yours['total_commission'])} "
        f"on {yours['order_count']} order(s). "
        f"{peer_label} earned {_inr(theirs['total_commission'])} "
        f"on {theirs['order_count']} order(s).",
    ]
    if diff > 0:
        parts.append(f"They earned {_inr(diff)} more than you this month.")
        reasons = []
        if (
            theirs["quota_attainment_pct"] is not None
            and yours["quota_attainment_pct"] is not None
            and theirs["quota_attainment_pct"] > yours["quota_attainment_pct"]
        ):
            reasons.append(
                f"they achieved {theirs['quota_attainment_pct']:.0f}% of quota "
                f"vs your {yours['quota_attainment_pct']:.0f}%"
            )
        if theirs["total_sales"] > yours["total_sales"]:
            reasons.append(
                f"their order volume was {_inr(theirs['total_sales'])} "
                f"vs your {_inr(yours['total_sales'])}"
            )
        if reasons:
            parts.append(" Likely reasons: " + "; ".join(reasons) + ".")
        else:
            parts.append(
                " Differences may come from commission rules, product mix, or rate tiers."
            )
    elif diff < 0:
        parts.append(f"You earned {_inr(-diff)} more than them this month.")
    else:
        parts.append("You both earned the same total this month.")

    return {"answer": "".join(parts), "peer": peer.employee_id}


def _answer_quota_question(commission, request):
    profile = get_request_profile(request)
    order = commission.sale.order if commission.sale_id else None
    if not profile or not order:
        return None

    start, end = _order_period_bounds(order)
    stats = _period_sales_and_commission(profile, start, end)
    target = stats["quota_target"]
    if target <= 0:
        return {
            "answer": (
                "No personal target is set on your profile for this period. "
                "An admin can add one in User Setup."
            ),
        }
    attainment = stats["quota_attainment_pct"]
    att_text = f"{attainment:.0f}%" if attainment is not None else "—"
    return {
        "answer": (
            f"For {start.strftime('%B %Y')}, your sales are {_inr(stats['total_sales'])} "
            f"against a target of {_inr(target)} ({att_text} attainment). "
            f"Commission earned in this period: {_inr(stats['total_commission'])}."
        ),
    }


def _answer_status_question(commission):
    status = commission.status or "calculated"
    labels = {
        "calculated": "Calculated — pending manager review.",
        "manager_approved": "Manager approved — pending finance approval.",
        "approved": "Finance approved — ready for payout.",
        "paid": "Paid — included in a payout run.",
    }
    detail = labels.get(status, status.replace("_", " ").title())
    return {
        "answer": (
            f"This commission status is {status.replace('_', ' ')}. {detail} "
            f"Amount: {_inr(commission.commission_amount)}."
        ),
    }


def _answer_contextual(question, explanation, commission):
    """Answer open-ended questions using commission breakdown context."""
    lines = explanation.get("lines", [])
    matched = _match_explanation_lines(question, lines)
    if matched:
        return {
            "answer": _format_lines_answer("Here's what applies to your question:", matched),
            "lines": matched,
        }

    lower = question.lower()
    summary = explanation.get("summary", "")

    if re.match(r"^(hi|hello|hey|thanks|thank you)\b", lower):
        return {
            "answer": (
                f"Hello! {summary} "
                "You can ask about rates, rules, quota, payout status, or comparisons with other reps."
            ),
        }

    facts = [f"{line['label']}: {line['display']}" for line in lines[:8]]
    fact_text = "; ".join(facts) if facts else summary
    return {
        "answer": (
            f"{summary} "
            f"From your commission data: {fact_text}. "
            "If something still looks incorrect, open a dispute from Incentive Details."
        ),
        "lines": lines,
    }


def answer_commission_question(commission: Commission, question: str, request) -> dict:
    """Natural-language answers via LLM grounded on commission data."""
    q = (question or "").strip()
    if not q:
        return {
            "answer": (
                "Ask anything about this commission — calculation, quota, payout, "
                "how to earn more, or comparisons with teammates."
            ),
        }

    explanation = build_commission_explanation(commission)
    if explanation.get("error"):
        return {"answer": explanation["error"]}

    from .commission_ai import ask_commission_ai

    return ask_commission_ai(commission, q, request, explanation)


def get_request_profile(request):
    from .permissions import get_request_user_profile

    return get_request_user_profile(request)


def simulate_what_if(request, extra_sales: Decimal, start_date, end_date) -> dict:
    """Estimate additional commission if the rep closes extra sales this period."""
    profile = get_request_profile(request)
    if not profile:
        return {"error": "User profile not found."}

    start = parse_date(start_date)
    end = parse_date(end_date)
    if not start or not end:
        return {"error": "Invalid start_date or end_date (use YYYY-MM-DD)."}
    if end < start:
        return {"error": "end_date must be on or after start_date."}

    extra_sales = _decimal(extra_sales)
    if extra_sales <= 0:
        return {"error": "Enter a positive extra sales amount."}

    order_date = end
    plan, _ = resolve_compensation_plan(
        Order(
            sales_amount=extra_sales,
            order_date=order_date,
            employee_id=profile.employee_id,
            organization_id=profile.organization_id,
            position_name=profile.position_name or "",
        )
    )
    if not plan:
        plan = (
            CompensationPlan.objects.filter(
                status="Active",
                role__iexact=profile.role or "",
                organization=profile.organization,
            )
            .order_by("-updated_at")
            .first()
        )
    if not plan:
        return {
            "error": "No active compensation plan found for your role.",
        }

    projected = _calculate_amount_for_plan(plan, extra_sales)

    dummy_order = Order(
        sales_amount=extra_sales,
        order_date=order_date,
        employee_id=profile.employee_id,
        organization_id=profile.organization_id,
        position_name=profile.position_name or "",
    )
    projected, _, _, _ = apply_commission_rules(
        plan, dummy_order, profile, projected
    )

    current = _period_sales_and_commission(profile, start, end)

    return {
        "extra_sales": str(extra_sales),
        "projected_commission": str(projected.quantize(Decimal("0.01"))),
        "current_period_commission": str(current["total_commission"]),
        "projected_total_commission": str(
            (current["total_commission"] + projected).quantize(Decimal("0.01"))
        ),
        "plan_name": plan.plan_name,
        "summary": (
            f"If you sell {_inr(extra_sales)} more this period under plan “{plan.plan_name}”, "
            f"you could earn about {_inr(projected)} additional commission "
            f"(≈ {_inr(current['total_commission'] + projected)} total for the period)."
        ),
    }

