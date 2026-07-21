"""Plan period helpers.

Plan *versions* use free-form effective date ranges (quarter, year, etc.).
Commission *payout aggregation* is still monthly (employee-month totals).
"""

import calendar
from datetime import date, datetime

from django.db import models


def parse_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()[:10]
    return datetime.strptime(text, "%Y-%m-%d").date()


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def normalize_monthly_plan_dates(start_value, end_value=None):
    """
    Legacy helper: snap dates to a single calendar month.

    Prefer free-form ranges for new versioned plans. Kept for older callers
    that still expect month windows.
    """
    start = parse_date(start_value)
    if not start:
        raise ValueError("effective_start_date is required")

    if end_value:
        end = parse_date(end_value)
        if end and (end.year != start.year or end.month != start.month):
            raise ValueError(
                "Compensation plans must fit within one calendar month. "
                "Use the 1st through last day of that month only."
            )

    return month_bounds(start.year, start.month)


def monthly_plan_filter(order_date) -> models.Q:
    """
    Legacy plan filter: match plans whose effective_start is in the same
    calendar month as the order. Used only as a fallback when a plan has
    no Published versions.
    """
    if not order_date:
        return models.Q()
    in_month = models.Q(
        effective_start_date__year=order_date.year,
        effective_start_date__month=order_date.month,
        effective_start_date__lte=order_date,
    )
    end_ok = models.Q(effective_end_date__gte=order_date) | models.Q(
        effective_end_date__isnull=True
    )
    return in_month & end_ok


