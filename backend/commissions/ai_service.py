"""Production-safe OpenAI-compatible JSON client for Incentra AI features."""

from __future__ import annotations

import json
import logging
from urllib import error, request

from django.conf import settings

from .commission_ai import (
    CommissionAIError,
    _assert_http_url,
    _resolve_ai_runtime,
    ai_setup_status,
)

logger = logging.getLogger("commissions")


class AIServiceError(Exception):
    """Safe, user-facing AI service failure."""


MAX_PROMPT_CHARS = int(getattr(settings, "COMMISSION_AI_MAX_PROMPT_CHARS", 24000))
MAX_RESPONSE_CHARS = int(getattr(settings, "COMMISSION_AI_MAX_RESPONSE_CHARS", 48000))


def feature_enabled(name, default=False):
    if not getattr(settings, "COMMISSION_AI_ENABLED", True):
        return False
    return bool(getattr(settings, name, default))


def ai_runtime_status():
    return ai_setup_status()


def _truncate(value, limit):
    text = str(value or "")
    return text[:limit]


def _extract_json_object(content):
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIServiceError("AI returned text instead of JSON.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIServiceError("AI returned invalid JSON.") from exc


def call_json_ai(*, system_prompt, user_payload, schema_hint, temperature=0.2, max_tokens=1800):
    runtime = _resolve_ai_runtime()
    if not runtime:
        raise AIServiceError("AI provider is not configured.")

    facts = _truncate(
        json.dumps(user_payload, default=str, separators=(",", ":")),
        MAX_PROMPT_CHARS,
    )
    payload = {
        "model": runtime["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Return only valid JSON. No markdown. No prose outside JSON.\n\n"
                    f"JSON schema guidance:\n{schema_hint}\n\n"
                    f"Input facts:\n{facts}"
                ),
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload).encode("utf-8")
    try:
        endpoint = _assert_http_url(f"{runtime['base_url']}/chat/completions")
    except CommissionAIError as exc:
        raise AIServiceError(str(exc)) from exc
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {runtime['api_key']}",
        },
        method="POST",
    )
    timeout = int(getattr(settings, "COMMISSION_AI_TIMEOUT", 45))
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8")[:MAX_RESPONSE_CHARS])
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        logger.error("AI HTTP %s: %s", exc.code, detail)
        raise AIServiceError("AI provider rejected the request. Check provider/model settings.") from exc
    except error.URLError as exc:
        logger.error("AI network error: %s", exc)
        raise AIServiceError("Could not reach the AI provider.") from exc
    except TimeoutError as exc:
        raise AIServiceError("AI provider timed out.") from exc
    except json.JSONDecodeError as exc:
        raise AIServiceError("AI provider returned an invalid response.") from exc

    choices = data.get("choices") or []
    if not choices:
        raise AIServiceError("AI provider returned no choices.")
    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise AIServiceError("AI provider returned an empty response.")
    parsed = _extract_json_object(content)
    return parsed, {"provider": runtime["provider"], "model": runtime["model"]}
