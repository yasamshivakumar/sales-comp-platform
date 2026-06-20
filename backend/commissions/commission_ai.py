"""LLM-powered commission Q&A — answers from live commission data, not fixed templates."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from urllib import error, request

from django.conf import settings

from .commission_explanation import (
    _order_period_bounds,
    _period_sales_and_commission,
    get_request_profile,
)
from .currencies import format_currency_amount, normalize_currency
from .models import UserProfile
from .services import _get_user_profile_for_order

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Incentra's AI sales compensation assistant — a real conversational assistant, not a FAQ bot.

You receive accurate facts about ONE commission row the user is viewing. Answer every question naturally in plain English.

Ground rules:
- Use ONLY the facts provided. Never invent numbers, names, rates, or policies.
- Write like a helpful colleague: warm for greetings/small talk, precise for commission questions.
- For "hi", "how are you", etc.: respond naturally in 1–2 sentences, then briefly mention what you can help with on this commission (use the real amount and order from the facts).
- For commission questions: explain clearly using the breakdown and summary. Use the currency shown in the facts for amounts.
- Month-to-date totals in current_period are for the whole month; this_commission is the specific row being viewed — do not confuse them.
- Never quote JSON keys, field names, or say "according to the context".
- Do not do math or projections unless the user asks for them.
- If facts are missing, say so honestly instead of guessing.
- Keep answers concise unless the user asks for detail."""


class CommissionAIError(Exception):
    """Raised when the LLM API call fails."""


def _ollama_installed_models(timeout=2) -> list[str]:
    base = getattr(settings, "COMMISSION_AI_OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    root = base.replace("/v1", "")
    try:
        with request.urlopen(f"{root}/api/tags", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = []
        for item in data.get("models") or []:
            name = item.get("name") or item.get("model")
            if name:
                names.append(name.split(":")[0] if ":" in name else name)
                names.append(name)
        return names
    except (error.URLError, error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return []


def _ollama_has_model(model_name: str) -> bool:
    if not model_name:
        return False
    target = model_name.lower()
    target_base = target.split(":")[0]
    for name in _ollama_installed_models():
        lower = name.lower()
        if lower == target or lower.startswith(f"{target_base}:") or lower == target_base:
            return True
    return False


def _probe_ollama(timeout=2) -> bool:
    base = getattr(settings, "COMMISSION_AI_OLLAMA_URL", "http://localhost:11434/v1").rstrip("/")
    root = base.replace("/v1", "")
    try:
        with request.urlopen(f"{root}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except (error.URLError, error.HTTPError, TimeoutError, OSError):
        return False


def _resolve_ai_runtime():
    """
    Pick OpenAI or Ollama based on COMMISSION_AI_PROVIDER and available credentials.
    Returns dict with base_url, api_key, model, provider — or None if nothing is configured.
    """
    provider = getattr(settings, "COMMISSION_AI_PROVIDER", "auto").lower()
    openai_key = (getattr(settings, "COMMISSION_AI_API_KEY", "") or "").strip()

    if provider == "openai":
        if not openai_key:
            return None
        return {
            "base_url": settings.COMMISSION_AI_BASE_URL.rstrip("/"),
            "api_key": openai_key,
            "model": settings.COMMISSION_AI_MODEL,
            "provider": "openai",
        }

    if provider == "ollama":
        if not _probe_ollama():
            return None
        return {
            "base_url": settings.COMMISSION_AI_OLLAMA_URL.rstrip("/"),
            "api_key": "ollama",
            "model": settings.COMMISSION_AI_OLLAMA_MODEL,
            "provider": "ollama",
        }

    # auto: prefer OpenAI when key exists, else local Ollama
    if openai_key:
        return {
            "base_url": settings.COMMISSION_AI_BASE_URL.rstrip("/"),
            "api_key": openai_key,
            "model": settings.COMMISSION_AI_MODEL,
            "provider": "openai",
        }
    if _probe_ollama():
        return {
            "base_url": settings.COMMISSION_AI_OLLAMA_URL.rstrip("/"),
            "api_key": "ollama",
            "model": settings.COMMISSION_AI_OLLAMA_MODEL,
            "provider": "ollama",
        }
    return None


def ai_setup_status() -> dict:
    """Whether Ask AI can run, and how to enable it."""
    if not getattr(settings, "COMMISSION_AI_ENABLED", True):
        return {
            "configured": False,
            "provider": None,
            "message": "The AI assistant is disabled (COMMISSION_AI_ENABLED=False).",
        }

    runtime = _resolve_ai_runtime()
    if runtime:
        if runtime["provider"] == "ollama" and not _ollama_has_model(runtime["model"]):
            model = runtime["model"]
            return {
                "configured": False,
                "provider": "ollama",
                "message": (
                    f"Ollama is running but model '{model}' is not downloaded yet.\n"
                    f"Open a terminal and run: ollama pull {model}\n"
                    "Keep the Ollama app open, then try Ask AI again."
                ),
            }
        return {
            "configured": True,
            "provider": runtime["provider"],
            "model": runtime["model"],
        }

    return {
        "configured": False,
        "provider": None,
        "message": (
            "Ask AI needs an LLM connection. Choose one:\n"
            "• Ollama (free, local, no API key) — install from ollama.com, run "
            "`ollama pull llama3.2:1b`, keep Ollama running, set "
            "COMMISSION_AI_PROVIDER=ollama in backend/.env, then restart.\n"
            "• OpenAI (cloud) — add OPENAI_API_KEY=sk-... to backend/.env "
            "(get a key at platform.openai.com/api-keys), set "
            "COMMISSION_AI_PROVIDER=openai, then restart."
        ),
    }


def commission_ai_enabled() -> bool:
    if not getattr(settings, "COMMISSION_AI_ENABLED", True):
        return False
    return _resolve_ai_runtime() is not None


def _decimal_str(value) -> str:
    if value is None:
        return "0"
    return str(Decimal(str(value)))


def _next_month_label(order_date) -> str:
    from dateutil.relativedelta import relativedelta

    start = order_date.replace(day=1) + relativedelta(months=1)
    return start.strftime("%B %Y")


def _teammate_snapshots(org_id, start, end, exclude_email=None, limit=5, currency=None):
    qs = UserProfile.objects.filter(organization_id=org_id).order_by("name")[:limit]
    snapshots = []
    for peer in qs:
        if exclude_email and peer.email == exclude_email:
            continue
        stats = _period_sales_and_commission(peer, start, end)
        snapshots.append(
            {
                "name": peer.name or peer.employee_id,
                "employee_id": peer.employee_id,
                "period_sales": _decimal_str(stats["total_sales"]),
                "period_commission": _decimal_str(stats["total_commission"]),
                "order_count": stats["order_count"],
                "quota_target": _decimal_str(stats["quota_target"]),
                "quota_attainment_pct": stats["quota_attainment_pct"],
                "currency": currency,
            }
        )
    return snapshots


def _commission_owner_profile(commission, order):
    """Profile for the rep who earned this commission (not the logged-in viewer)."""
    if order:
        profile = _get_user_profile_for_order(order)
        if profile:
            return profile
    try:
        employee = commission.employee
        if employee and employee.email:
            return UserProfile.objects.filter(
                email__iexact=employee.email,
                organization=getattr(commission, "organization", None),
            ).first()
    except Exception:
        pass
    return None


def _format_money_display(amount, currency=None) -> str:
    try:
        return format_currency_amount(Decimal(str(amount)), normalize_currency(currency))
    except Exception:
        return format_currency_amount(amount, normalize_currency(currency))


def _build_context_narrative(context: dict) -> str:
    """Plain-English fact sheet for the LLM — not a canned answer."""
    rep = context.get("rep") or {}
    comm = context.get("this_commission") or {}
    period = context.get("current_period") or {}
    parts = []

    rep_name = rep.get("name") or rep.get("employee_id") or "The rep"
    currency = comm.get("currency")
    amount = _format_money_display(comm.get("amount", "0"), currency)
    order_id = comm.get("order_id") or "—"
    parts.append(f"{rep_name} is viewing a commission of {amount} on order {order_id}.")

    if comm.get("summary"):
        parts.append(comm["summary"])

    if comm.get("plan_name"):
        parts.append(f"Compensation plan: {comm['plan_name']}.")

    if comm.get("status"):
        parts.append(f"Payout status: {comm['status'].replace('_', ' ')}.")

    if period:
        parts.append(
            f"Month-to-date ({period.get('label', 'this month')}): "
            f"sales {_format_money_display(period.get('sales', 0), period.get('currency') or currency)}, "
            f"commission {_format_money_display(period.get('commission', 0), period.get('currency') or currency)}, "
            f"{period.get('order_count', 0)} order(s)."
        )
        if period.get("quota_target") and Decimal(str(period["quota_target"])) > 0:
            att = period.get("quota_attainment_pct")
            att_text = f"{att}%" if att is not None else "n/a"
            parts.append(
                f"Quota target {_format_money_display(period['quota_target'], period.get('currency') or currency)} "
                f"({att_text} attainment)."
            )

    breakdown = context.get("breakdown") or []
    if breakdown:
        steps = "; ".join(
            f"{line.get('label')}: {line.get('value')}"
            for line in breakdown[:6]
            if line.get("label")
        )
        if steps:
            parts.append(f"Calculation steps: {steps}.")

    return " ".join(parts)


def build_commission_context(commission, request, explanation) -> dict:
    """Structured facts for the LLM — grounded in database state."""
    order = commission.sale.order if commission.sale_id else None
    profile = _commission_owner_profile(commission, order) or get_request_profile(request)
    viewer = get_request_profile(request)
    plan = commission.compensation_plan
    currency = normalize_currency(getattr(order, "currency", None)) if order else normalize_currency(None)

    period = {}
    teammates = []
    next_period = None
    if order and profile:
        start, end = _order_period_bounds(order)
        stats = _period_sales_and_commission(profile, start, end)
        period = {
            "label": start.strftime("%B %Y"),
            "start_date": str(start),
            "end_date": str(end),
            "sales": _decimal_str(stats["total_sales"]),
            "commission": _decimal_str(stats["total_commission"]),
            "order_count": stats["order_count"],
            "quota_target": _decimal_str(stats["quota_target"]),
            "quota_attainment_pct": stats["quota_attainment_pct"],
            "currency": currency,
        }
        next_period = _next_month_label(order.order_date)
        if order.organization_id:
            teammates = _teammate_snapshots(
                order.organization_id, start, end, exclude_email=profile.email, currency=currency
            )

    effective_rate_pct = None
    if period.get("sales") and Decimal(period["sales"]) > 0:
        effective_rate_pct = float(
            Decimal(period["commission"]) / Decimal(period["sales"]) * 100
        )

    breakdown = [
        {
            "label": line.get("label"),
            "value": line.get("display"),
        }
        for line in explanation.get("lines", [])
    ]

    return {
        "rep": {
            "name": explanation.get("employee_name") or (profile.name if profile else None),
            "email": profile.email if profile else None,
            "employee_id": profile.employee_id if profile else None,
            "role": profile.role if profile else None,
            "personal_target": _decimal_str(profile.personal_target) if profile else None,
            "currency": currency,
        },
        "viewer_is_rep": bool(
            viewer and profile and viewer.email == profile.email
        ),
        "this_commission": {
            "id": commission.id,
            "amount": _decimal_str(commission.commission_amount),
            "currency": currency,
            "status": commission.status or "calculated",
            "order_id": explanation.get("order_id"),
            "order_date": explanation.get("order_date"),
            "plan_name": plan.plan_name if plan else None,
            "summary": explanation.get("summary"),
        },
        "breakdown": breakdown,
        "current_period": period,
        "next_period_label": next_period,
        "effective_commission_rate_pct": round(effective_rate_pct, 2)
        if effective_rate_pct is not None
        else None,
        "teammates_in_period": teammates,
        "ui_features": {
            "what_if_simulator": (
                "Rep can enter extra sales in the explanation panel to project commission."
            ),
            "disputes": "Rep can raise a dispute from Incentive Details if something looks wrong.",
        },
    }


def _call_chat_completion(question: str, context: dict, runtime: dict) -> str:
    narrative = _build_context_narrative(context)
    payload = {
        "model": runtime["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Facts:\n{narrative}\n\n"
                    f"Structured data:\n{json.dumps(context, separators=(',', ':'))}\n\n"
                    f"Rep's question: {question}"
                ),
            },
        ],
        "temperature": 0.55,
        "max_tokens": 600,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{runtime['base_url']}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {runtime['api_key']}",
        },
        method="POST",
    )
    timeout = getattr(settings, "COMMISSION_AI_TIMEOUT", 45)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        logger.error("Commission AI HTTP %s: %s", exc.code, detail)
        detail_lower = detail.lower()
        if exc.code == 404 and "model" in detail_lower and "not found" in detail_lower:
            model = runtime.get("model", "the configured model")
            raise CommissionAIError(
                f"Ollama model '{model}' is not installed. "
                f"Open a terminal and run: ollama pull {model} "
                "(then restart Ask AI)."
            ) from exc
        raise CommissionAIError(
            "The AI assistant is temporarily unavailable. Please try again in a moment."
        ) from exc
    except error.URLError as exc:
        logger.error("Commission AI network error: %s", exc)
        raise CommissionAIError(
            "Could not reach the AI service. Check your network or API configuration."
        ) from exc

    choices = data.get("choices") or []
    if not choices:
        raise CommissionAIError("The AI returned an empty response.")
    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise CommissionAIError("The AI returned an empty response.")
    return content


def _offline_answer(explanation: dict) -> dict:
    status = ai_setup_status()
    return {
        "answer": status.get("message", "AI assistant is not configured."),
        "source": "offline",
        "ai": status,
    }


def ask_commission_ai(commission, question: str, request, explanation: dict) -> dict:
    """Answer a natural-language question using an LLM grounded on commission data."""
    runtime = _resolve_ai_runtime()
    if not runtime or not getattr(settings, "COMMISSION_AI_ENABLED", True):
        result = _offline_answer(explanation)
        return result

    context = build_commission_context(commission, request, explanation)

    try:
        answer = _call_chat_completion(question, context, runtime)
        return {
            "answer": answer,
            "source": "ai",
            "provider": runtime["provider"],
            "ai": ai_setup_status(),
        }
    except CommissionAIError as exc:
        return {"answer": str(exc), "source": "error", "ai": ai_setup_status()}
    except Exception:
        logger.exception("Unexpected commission AI failure")
        return {
            "answer": (
                "Something went wrong while generating an AI answer. "
                "Please try again or review the breakdown above."
            ),
            "source": "error",
            "ai": ai_setup_status(),
        }
