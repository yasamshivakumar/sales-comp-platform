import csv
import io
import logging

from django.utils import timezone

from .models import ImportJob
from .integrations.order_sync import process_orders_rows

from django.conf import settings

logger = logging.getLogger("commissions")


def should_use_async_import(row_count):
    if not settings.CELERY_BROKER_URL:
        return False
    return settings.USE_ASYNC_IMPORTS and row_count >= settings.ASYNC_IMPORT_MIN_ROWS


# Re-export for backward compatibility
DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%m/%d/%Y",
]


def commission_skip_reason(order):
    from .integrations.order_sync import commission_skip_reason as _reason

    return _reason(order)


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
    return process_users_rows(
        organization,
        rows,
        allow_updates=True,
        login_via_invite=False,
        strict_csv=True,
    )


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
