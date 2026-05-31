"""
Required vs optional fields for commission data entry.

USER SETUP (required): email, role, employee_id, name
ORDERS (required): order_id, employee_id, sales_amount, order_date
COMPENSATION PLAN (required): plan_name, role, status, plan_basis,
    effective_start_date, commission_table_type
All other fields are optional.
"""

from rest_framework.exceptions import ValidationError


def _missing(label, field):
    raise ValidationError({field: f"{label} is required."})


def validate_user_profile_fields(data, partial=False):
    if not partial or "email" in data:
        if not str(data.get("email", "")).strip():
            _missing("Email", "email")
    if not partial or "role" in data:
        if not str(data.get("role", "")).strip():
            _missing("Role", "role")
    if not partial or "employee_id" in data:
        if not str(data.get("employee_id", "")).strip():
            _missing("Employee ID", "employee_id")
    if not partial or "name" in data:
        if not str(data.get("name", "")).strip():
            _missing("Name", "name")


def validate_order_fields(data, partial=False):
    if not partial or "order_id" in data:
        if not str(data.get("order_id", "")).strip():
            _missing("Order ID", "order_id")
    if not partial or "employee_id" in data:
        if not str(data.get("employee_id", "")).strip():
            _missing("Employee ID", "employee_id")
    if not partial or "sales_amount" in data:
        if data.get("sales_amount") in (None, ""):
            _missing("Sales amount", "sales_amount")
    if not partial or "order_date" in data:
        if not data.get("order_date"):
            _missing("Order date", "order_date")


def validate_compensation_plan_fields(data, partial=False):
    if not partial or "plan_name" in data:
        if not str(data.get("plan_name", "")).strip():
            _missing("Plan name", "plan_name")
    if not partial or "role" in data:
        if not str(data.get("role", "")).strip():
            _missing("Role", "role")
    if not partial or "status" in data:
        if not str(data.get("status", "")).strip():
            _missing("Status", "status")
    if not partial or "plan_basis" in data:
        if not str(data.get("plan_basis", "")).strip():
            _missing("Plan basis", "plan_basis")
    if not partial or "effective_start_date" in data:
        if not data.get("effective_start_date"):
            _missing("Effective start date", "effective_start_date")
    table_type = data.get("commission_table_type") or data.get("table_type")
    if not partial or "commission_table_type" in data or "table_type" in data:
        if not str(table_type or "").strip():
            _missing("Commission table type", "commission_table_type")


def normalize_compensation_plan_payload(data):
    """Map API/UI aliases to model fields."""
    normalized = dict(data)
    if "table_type" in normalized and "commission_table_type" not in normalized:
        raw = str(normalized.pop("table_type")).strip().lower()
        normalized["commission_table_type"] = "FLAT" if raw == "flat" else "RATE"
    elif "commission_table_type" in normalized:
        raw = str(normalized["commission_table_type"]).strip().upper()
        if raw not in ("RATE", "FLAT"):
            raw = "RATE"
        normalized["commission_table_type"] = raw
    if not normalized.get("status"):
        normalized["status"] = "Active"
    if not normalized.get("plan_basis"):
        normalized["plan_basis"] = "Role"
    return normalized
