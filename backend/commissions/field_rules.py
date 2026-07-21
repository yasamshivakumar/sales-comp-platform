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


def find_user_profile_duplicates(organization, email, employee_id, exclude_pk=None):
    """
    Return human-readable duplicate errors for email / employee_id within an org.
    Used for manual create and CSV upload.
    """
    from .models import UserProfile

    qs = UserProfile.objects.all()
    if organization is not None:
        qs = qs.filter(organization=organization)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    errors = []
    email = str(email or "").strip()
    employee_id = str(employee_id or "").strip()

    if email:
        match = qs.filter(email__iexact=email).first()
        if match:
            label = match.name or match.employee_id or match.email
            errors.append(
                f"Email '{email}' is already used by {label}."
            )

    if employee_id:
        match = (
            qs.filter(employee_id__iexact=employee_id)
            .exclude(employee_id="")
            .first()
        )
        if match:
            label = match.name or match.email or match.employee_id
            errors.append(
                f"Employee ID '{employee_id}' is already assigned to {label}."
            )

    return errors


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
    """Map API/UI aliases to model fields and normalize effective date ranges.

    Versions may span any date range (quarter, year, etc.). A legacy
    ``comp_period=YYYY-MM`` still expands to that calendar month for
    backward compatibility.
    """
    from datetime import date as date_cls

    from .plan_periods import month_bounds, parse_date

    normalized = dict(data)
    if "table_type" in normalized and "commission_table_type" not in normalized:
        raw = str(normalized.pop("table_type")).strip().lower()
        if raw == "flat":
            normalized["commission_table_type"] = "FLAT"
        elif raw == "lookup":
            normalized["commission_table_type"] = "LOOKUP"
        else:
            normalized["commission_table_type"] = "RATE"
    elif "commission_table_type" in normalized:
        raw = str(normalized["commission_table_type"]).strip().upper()
        if raw not in ("RATE", "FLAT", "LOOKUP"):
            raw = "RATE"
        normalized["commission_table_type"] = raw

    if not normalized.get("status"):
        normalized["status"] = "Active"
    if not normalized.get("plan_basis"):
        normalized["plan_basis"] = "Role"

    # Legacy UI may send comp_period=YYYY-MM from month picker
    comp_period = normalized.pop("comp_period", None) or normalized.pop("plan_month", None)
    if comp_period and not normalized.get("effective_start_date"):
        text = str(comp_period).strip()
        if len(text) == 7 and text[4] == "-":
            y, m = int(text[:4]), int(text[5:7])
            start, end = month_bounds(y, m)
            normalized["effective_start_date"] = start
            if not normalized.get("effective_end_date"):
                normalized["effective_end_date"] = end

    start = parse_date(normalized.get("effective_start_date"))
    end = parse_date(normalized.get("effective_end_date"))
    if start:
        normalized["effective_start_date"] = start
        if end is not None:
            if end < start:
                raise ValueError("effective_end_date cannot be before effective_start_date")
            normalized["effective_end_date"] = end
        normalized["pay_period_type"] = normalized.get("pay_period_type") or "Monthly"

    return normalized
