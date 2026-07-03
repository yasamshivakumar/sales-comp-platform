"""
CRM-agnostic order import: one row per CRM deal, deduped by order_id (CRM id).

Each import is transaction-safe. Unchanged existing orders are skipped (no duplicate
rows, no redundant commission recalculation). New or updated Success orders trigger
monthly aggregate commission recalculation for that employee/period.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction

from ..models import Order
from ..services import (
    calculate_commission_for_order,
    commission_skip_reason_for_status,
    explain_plan_resolution_failure,
    resolve_compensation_plan,
    _profile_for_employee,
)
from ..currencies import normalize_currency
from .employee_ids import normalize_crm_id

logger = logging.getLogger("commissions")

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%m/%d/%Y",
]


def parse_order_date(value):
    from datetime import datetime

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def commission_skip_reason(order):
    """Human-readable reason when calculate_commission_for_order returns None."""
    status_reason = commission_skip_reason_for_status(order)
    if status_reason:
        return status_reason
    plan, _source = resolve_compensation_plan(order)
    if not plan:
        return explain_plan_resolution_failure(order)
    return "Commission amount calculated as zero (check plan rate tiers / thresholds)."


# CRM-sourced fields used to detect whether an existing order needs updating.
CRM_UNCHANGED_FIELDS = (
    "order_date",
    "employee_id",
    "sales_amount",
    "order_status",
)


def _parse_sales_amount(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_order_date_value(value):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    return parse_order_date(value)


def build_order_defaults(organization, row):
    """Build Order field defaults from a normalized import row."""
    employee_id = str(row.get("employee_id", "")).strip()
    order_date = _parse_order_date_value(row.get("order_date", ""))
    sales_amount = _parse_sales_amount(row.get("sales_amount", 0))
    order_model_fields = {field.name for field in Order._meta.get_fields()}

    defaults = {"organization": organization}
    if "order_date" in order_model_fields and order_date is not None:
        defaults["order_date"] = order_date
    if "employee_id" in order_model_fields:
        defaults["employee_id"] = employee_id
    if "position_name" in order_model_fields:
        defaults["position_name"] = str(row.get("position_name", "")).strip()
    if "sales_amount" in order_model_fields:
        defaults["sales_amount"] = sales_amount
    if "order_status" in order_model_fields:
        defaults["order_status"] = (
            str(row.get("order_status", "Booked")).strip() or "Booked"
        )
    if "needs_recalculation" in order_model_fields:
        defaults["needs_recalculation"] = False

    for field_name in ("product_name", "service_name", "distribution"):
        if field_name in row and field_name in order_model_fields:
            defaults[field_name] = str(row.get(field_name, "")).strip()

    for field_name in ("region", "customer_segment", "business_group", "currency"):
        if field_name in row and field_name in order_model_fields:
            value = str(row.get(field_name, "")).strip()
            if field_name == "currency" and value:
                defaults[field_name] = normalize_currency(value)
            elif value:
                defaults[field_name] = value

    profile = _profile_for_employee(employee_id, organization)
    from ..services import normalize_order_region_fields

    normalize_order_region_fields(defaults, profile=profile)

    territory_id = row.get("territory") or row.get("territory_id")
    if territory_id and "territory" in order_model_fields:
        from ..models import Territory

        if not Territory.objects.filter(
            pk=territory_id,
            organization=organization,
        ).exists():
            raise ValueError("Territory does not belong to this organization.")
        defaults["territory_id"] = territory_id

    if (
        "quantity" in row
        and "quantity" in order_model_fields
        and str(row.get("quantity", "")).strip()
    ):
        defaults["quantity"] = float(row.get("quantity"))

    crm_owner_id = (
        row.get("crm_owner_id")
        or row.get("hubspot_owner_id")
        or row.get("crm_user_id")
    )
    if crm_owner_id and "crm_owner_id" in order_model_fields:
        defaults["crm_owner_id"] = normalize_crm_id(crm_owner_id) or str(crm_owner_id).strip()

    return defaults


def _field_values_equal(existing, field_name, new_value):
    current = getattr(existing, field_name, None)
    if isinstance(current, Decimal) and isinstance(new_value, Decimal):
        return current == new_value
    if field_name == "order_date":
        return current == new_value
    return str(current or "") == str(new_value or "")


def order_unchanged(existing, defaults):
    """True when an existing order already matches the incoming CRM row."""
    for field_name in CRM_UNCHANGED_FIELDS:
        if field_name not in defaults:
            continue
        if not _field_values_equal(existing, field_name, defaults[field_name]):
            return False
    crm_owner = defaults.get("crm_owner_id")
    if crm_owner and getattr(existing, "crm_owner_id", None):
        if normalize_crm_id(existing.crm_owner_id) != normalize_crm_id(crm_owner):
            return False
    return True


@transaction.atomic
def import_order_row(
    organization,
    row,
    *,
    crm_provider=None,
    integration=None,
    row_index=1,
):
    """
    Import one order row. Dedupes on (organization, order_id) where order_id is the CRM id.

    Returns dict with action: created | updated | unchanged.
    """
    order_id = str(row.get("order_id", "")).strip()
    if not order_id:
        raise ValueError("order_id is required")

    employee_id = str(row.get("employee_id", "")).strip()
    if not employee_id:
        raise ValueError("employee_id is required")

    if not row.get("order_date"):
        raise ValueError("order_date is required")

    defaults = build_order_defaults(organization, row)
    if not defaults.get("order_date"):
        raise ValueError(f"Invalid order_date format: {row.get('order_date')}")

    order_model_fields = {field.name for field in Order._meta.get_fields()}
    if crm_provider and "crm_provider" in order_model_fields:
        defaults["crm_provider"] = crm_provider
    if integration and "external_integration" in order_model_fields:
        defaults["external_integration"] = integration

    existing = (
        Order.objects.select_for_update()
        .filter(organization=organization, order_id=order_id)
        .first()
    )
    if existing and order_unchanged(existing, defaults):
        return {
            "action": "unchanged",
            "order": existing,
            "commission": None,
            "order_id": order_id,
            "employee_id": employee_id,
            "order_date": str(defaults.get("order_date")),
            "row_index": row_index,
        }

    order, created = Order.objects.update_or_create(
        organization=organization,
        order_id=order_id,
        defaults=defaults,
    )
    action = "created" if created else "updated"

    commission = None
    if order.order_status == "Success":
        commission = calculate_commission_for_order(order)

    return {
        "action": action,
        "order": order,
        "commission": commission,
        "order_id": order_id,
        "employee_id": employee_id,
        "order_date": str(order.order_date),
        "row_index": row_index,
    }


def process_orders_rows(organization, rows, *, crm_provider=None, integration=None):
    """Import order rows with per-row transactions and deduplication."""
    success = 0
    failed = 0
    created = 0
    updated = 0
    unchanged = 0
    commissions_created = 0
    commissions_skipped = 0
    errors = []
    commission_warnings = []

    for index, row in enumerate(rows, start=1):
        try:
            result = import_order_row(
                organization,
                row,
                crm_provider=crm_provider,
                integration=integration,
                row_index=index,
            )
            action = result["action"]
            if action == "created":
                created += 1
            elif action == "updated":
                updated += 1
            else:
                unchanged += 1

            commission = result.get("commission")
            if commission:
                commissions_created += 1
            elif action != "unchanged" and result.get("order"):
                commissions_skipped += 1
                order = result["order"]
                if len(commission_warnings) < 20:
                    commission_warnings.append(
                        {
                            "row": index,
                            "order_id": result["order_id"],
                            "employee_id": result["employee_id"],
                            "order_date": result["order_date"],
                            "reason": commission_skip_reason(order),
                        }
                    )
            success += 1
        except Exception as exc:
            failed += 1
            errors.append({"row": index, "error": str(exc)})
            logger.exception("Order import row %s failed", index)

    return {
        "success": success,
        "failed": failed,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "commissions_created": commissions_created,
        "commissions_skipped": commissions_skipped,
        "errors": errors[:20],
        "commission_warnings": commission_warnings,
        "total_rows": len(rows),
    }
