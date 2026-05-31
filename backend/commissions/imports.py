import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import ImportJob, Order
from .services import calculate_commission_for_order

from django.conf import settings

logger = logging.getLogger("commissions")


def should_use_async_import(row_count):
    if not settings.CELERY_BROKER_URL:
        return False
    return settings.USE_ASYNC_IMPORTS and row_count >= settings.ASYNC_IMPORT_MIN_ROWS

DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]


def parse_order_date(value):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def process_orders_csv(organization, decoded_csv):
    """
    Process order rows for one organization.
    Returns dict: success, failed, errors (max 20 in list).
    """
    csv_reader = csv.DictReader(io.StringIO(decoded_csv))
    rows = list(csv_reader)

    success = 0
    failed = 0
    errors = []
    order_model_fields = {field.name for field in Order._meta.get_fields()}

    for index, row in enumerate(rows, start=2):
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

            for field_name in ("customer_name", "product_name", "service_name"):
                if field_name in row and field_name in order_model_fields:
                    defaults[field_name] = str(row.get(field_name, "")).strip()

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
            calculate_commission_for_order(order)
            success += 1
        except Exception as exc:
            failed += 1
            errors.append({"row": index, "error": str(exc)})
            logger.exception("Order import row %s failed", index)

    return {
        "success": success,
        "failed": failed,
        "errors": errors[:20],
        "total_rows": len(rows),
    }


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
