import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import ImportJob, Order
from .services import (
    calculate_commission_for_order,
    commission_skip_reason_for_status,
    explain_plan_resolution_failure,
    resolve_compensation_plan,
    _get_user_profile_for_order,
)

from django.conf import settings

logger = logging.getLogger("commissions")


def should_use_async_import(row_count):
    if not settings.CELERY_BROKER_URL:
        return False
    return settings.USE_ASYNC_IMPORTS and row_count >= settings.ASYNC_IMPORT_MIN_ROWS

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%m/%d/%Y",
]


def commission_skip_reason(order):
    """Human-readable reason when calculate_commission_for_order returns None."""
    status_reason = commission_skip_reason_for_status(order)
    if status_reason:
        return status_reason
    plan, _source = resolve_compensation_plan(order)
    if not plan:
        return explain_plan_resolution_failure(order)
    return "Commission amount calculated as zero (check plan rate tiers / thresholds)."


def parse_order_date(value):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def process_orders_rows(organization, rows):
    """Process order dict rows (same shape as CSV columns). Used by CSV and CRM sync."""
    success = 0
    failed = 0
    commissions_created = 0
    commissions_skipped = 0
    errors = []
    commission_warnings = []
    order_model_fields = {field.name for field in Order._meta.get_fields()}

    for index, row in enumerate(rows, start=1):
        try:
            order_id = str(row.get("order_id", "")).strip()
            if not order_id:
                raise ValueError("order_id is required")

            employee_id = str(row.get("employee_id", "")).strip()
            if not employee_id:
                raise ValueError("employee_id is required")

            order_date_value = row.get("order_date", "")
            if not order_date_value:
                raise ValueError("order_date is required")

            if hasattr(order_date_value, "isoformat"):
                order_date = order_date_value
            else:
                order_date = parse_order_date(order_date_value)
            if order_date is None:
                raise ValueError(f"Invalid order_date format: {order_date_value}")

            try:
                sales_amount = Decimal(str(row.get("sales_amount", 0) or 0))
            except (InvalidOperation, ValueError):
                sales_amount = Decimal("0")

            defaults = {"organization": organization}
            if "order_date" in order_model_fields:
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
            if "currency" in order_model_fields:
                defaults["currency"] = (
                    str(row.get("currency", "INR")).strip() or "INR"
                )
            if "needs_recalculation" in order_model_fields:
                defaults["needs_recalculation"] = False

            for field_name in ("product_name", "service_name", "distribution"):
                if field_name in row and field_name in order_model_fields:
                    defaults[field_name] = str(row.get(field_name, "")).strip()

            for field_name in ("region", "customer_segment", "business_group"):
                if field_name in row and field_name in order_model_fields:
                    defaults[field_name] = str(row.get(field_name, "")).strip()

            territory_id = row.get("territory") or row.get("territory_id")
            if territory_id and "territory" in order_model_fields:
                from .models import Territory

                if not Territory.objects.filter(
                    pk=territory_id,
                    organization=organization,
                ).exists():
                    raise ValueError(
                        "Territory does not belong to this organization."
                    )
                defaults["territory_id"] = territory_id

            if (
                "quantity" in row
                and "quantity" in order_model_fields
                and str(row.get("quantity", "")).strip()
            ):
                defaults["quantity"] = float(row.get("quantity"))

            order, _created = Order.objects.update_or_create(
                organization=organization,
                order_id=order_id,
                defaults=defaults,
            )
            commission = calculate_commission_for_order(order)
            if commission:
                commissions_created += 1
            else:
                commissions_skipped += 1
                if len(commission_warnings) < 20:
                    commission_warnings.append(
                        {
                            "row": index,
                            "order_id": order_id,
                            "employee_id": employee_id,
                            "order_date": str(order_date),
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
        "commissions_created": commissions_created,
        "commissions_skipped": commissions_skipped,
        "errors": errors[:20],
        "commission_warnings": commission_warnings,
        "total_rows": len(rows),
    }


def process_orders_csv(organization, decoded_csv):
    """
    Process order rows for one organization.
    Returns dict: success, failed, errors (max 20 in list).
    """
    csv_reader = csv.DictReader(io.StringIO(decoded_csv))
    rows = list(csv_reader)
    result = process_orders_rows(organization, rows)
    return result


def process_users_csv(organization, decoded_csv):
    """Process user setup rows for one organization."""
    from .integrations.user_import import process_users_rows

    csv_reader = csv.DictReader(io.StringIO(decoded_csv))
    rows = list(csv_reader)
    return process_users_rows(organization, rows, allow_updates=False)


def run_import_job(job_id):
    """Execute a stored ImportJob (orders CSV)."""
    job = ImportJob.objects.select_related("organization").get(pk=job_id)
    job.status = ImportJob.STATUS_PROCESSING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    try:
        with job.input_file.open("r") as handle:
            decoded = handle.read()
            if isinstance(decoded, bytes):
                decoded = decoded.decode("utf-8")

        if job.job_type == ImportJob.JOB_ORDERS:
            result = process_orders_csv(job.organization, decoded)
        elif job.job_type == ImportJob.JOB_USERS:
            result = process_users_csv(job.organization, decoded)
        else:
            raise ValueError(f"Unsupported job type: {job.job_type}")

        job.result = result
        job.status = ImportJob.STATUS_COMPLETED
        job.error_message = ""
    except Exception as exc:
        logger.exception("Import job %s failed", job_id)
        job.status = ImportJob.STATUS_FAILED
        job.error_message = str(exc)
        job.result = {}

    job.completed_at = timezone.now()
    job.save(
        update_fields=["status", "result", "error_message", "completed_at"]
    )
    return job
