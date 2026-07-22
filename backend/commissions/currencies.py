"""Supported currencies for orders, user profiles, and commission display."""

from decimal import Decimal, InvalidOperation

SUPPORTED_CURRENCIES = [
    {
        "code": "INR",
        "label": "INR — Indian Rupee",
        "locale": "en-IN",
        "symbol": "₹",
    },
    {
        "code": "USD",
        "label": "USD — US Dollar",
        "locale": "en-US",
        "symbol": "$",
    },
    {
        "code": "EUR",
        "label": "EUR — Euro",
        "locale": "de-DE",
        "symbol": "€",
    },
    {
        "code": "AUD",
        "label": "AUD — Australian Dollar",
        "locale": "en-AU",
        "symbol": "A$",
    },
]

SUPPORTED_CURRENCY_CODES = {item["code"] for item in SUPPORTED_CURRENCIES}
DEFAULT_CURRENCY = "INR"


def normalize_currency(code, default=DEFAULT_CURRENCY):
    normalized = str(code or "").strip().upper()
    if normalized in SUPPORTED_CURRENCY_CODES:
        return normalized
    return default


def currency_meta(code):
    normalized = normalize_currency(code)
    for item in SUPPORTED_CURRENCIES:
        if item["code"] == normalized:
            return item
    return SUPPORTED_CURRENCIES[0]


def format_currency_amount(amount, currency_code=DEFAULT_CURRENCY):
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal("0")
    meta = currency_meta(currency_code)
    formatted = f"{value:,.2f}"
    return f"{meta['symbol']}{formatted}"


def currency_choices_for_api():
    return [{"value": item["code"], "label": item["label"]} for item in SUPPORTED_CURRENCIES]


def active_currency_totals(rows, value_key="total"):
    """Drop zero totals and normalize currency codes for API responses."""
    cleaned = []
    for row in rows or []:
        amount = row.get(value_key, 0)
        try:
            numeric = float(amount or 0)
        except (TypeError, ValueError):
            numeric = 0
        if numeric <= 0:
            continue
        cleaned.append(
            {
                **row,
                "currency": normalize_currency(row.get("currency")),
                value_key: numeric,
            }
        )
    cleaned.sort(key=lambda item: item["currency"])
    return cleaned
