import logging

from celery import shared_task

from .emails import notify_admins
from .imports import run_import_job

logger = logging.getLogger("commissions")


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_import_job_task(self, job_id):
    try:
        job = run_import_job(job_id)
        if job.status == job.STATUS_COMPLETED:
            notify_admins(
                f"Incentra: {job.job_type} import #{job.id} completed",
                (
                    f"Organization: {job.organization.slug}\n"
                    f"File: {job.source_filename}\n"
                    f"Success: {job.result.get('success', 0)}\n"
                    f"Failed: {job.result.get('failed', 0)}\n"
                ),
            )
        return {"job_id": job_id, "status": job.status}
    except Exception as exc:
        logger.exception("Celery import job %s failed", job_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def run_auto_sync_for_integration_task(self, integration_id):
    from .integrations.sync import run_auto_sync_for_integration
    from .models import ExternalIntegration

    try:
        integration = ExternalIntegration.objects.get(pk=integration_id, is_active=True)
        return run_auto_sync_for_integration(integration)
    except Exception as exc:
        logger.exception("Auto sync task failed for integration %s", integration_id)
        raise self.retry(exc=exc)


@shared_task
def run_due_auto_integration_syncs_task():
    from .integrations.sync import run_due_auto_integration_syncs

    return run_due_auto_integration_syncs()
