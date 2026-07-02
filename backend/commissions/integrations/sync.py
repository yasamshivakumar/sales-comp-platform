"""Run pull/push sync jobs for external integrations."""

import logging
import secrets

from django.utils import timezone

from ..imports import process_orders_rows
from ..models import ExternalIntegration, IntegrationSyncLog
from .base import ConnectorError
from .employee_ids import resolve_crm_owner_to_employee_id
from .mapper import map_records, normalize_date_value
from .registry import get_connector
from .user_import import process_users_rows

logger = logging.getLogger("commissions")


def ensure_webhook_secret(integration):
    if integration.webhook_secret:
        return integration.webhook_secret
    integration.webhook_secret = secrets.token_urlsafe(24)
    integration.save(update_fields=["webhook_secret"])
    return integration.webhook_secret


def _section_config(integration, resource_type):
    return (integration.config or {}).get(resource_type) or {}


def _normalize_order_rows(rows):
    normalized = []
    for row in rows:
        item = dict(row)
        if item.get("order_date"):
            item["order_date"] = normalize_date_value(item["order_date"])
        normalized.append(item)
    return normalized


def _resolve_order_employee_ids(organization, rows, integration=None):
    """Map CRM owner ids from deals to Incentra employee_id before order import."""
    resolved = []
    for row in rows:
        item = dict(row)
        if not str(item.get("employee_id", "")).strip():
            crm_owner_id = (
                item.get("crm_owner_id")
                or item.get("hubspot_owner_id")
                or item.get("crm_user_id")
            )
            employee_id = resolve_crm_owner_to_employee_id(
                organization,
                crm_owner_id,
                integration=integration,
            )
            if not employee_id:
                raise ValueError(
                    f"No Incentra employee mapped for CRM owner id {crm_owner_id}. "
                    "Run user sync first, or check that the deal owner exists in HubSpot "
                    "and matches an employee email in Incentra."
                )
            item["employee_id"] = employee_id
        resolved.append(item)
    return resolved


def run_pull_sync(integration, sync_type, triggered_by=None, limit=None):
    """Pull users or orders from CRM and import via existing pipelines."""
    log = IntegrationSyncLog.objects.create(
        integration=integration,
        sync_type=sync_type,
        status=IntegrationSyncLog.STATUS_RUNNING,
        triggered_by=triggered_by,
    )
    try:
        connector = get_connector(integration)
        section = _section_config(integration, sync_type)
        field_map = section.get("field_map") or {}
        defaults = section.get("defaults") or {}

        raw_records = connector.fetch_records(sync_type, limit=limit)
        mapped = map_records(raw_records, field_map, defaults=defaults)
        log.records_fetched = len(mapped)

        org = integration.organization
        if sync_type == IntegrationSyncLog.SYNC_USERS:
            result = process_users_rows(org, mapped)
            result["fetched"] = [
                {
                    "email": row.get("email"),
                    "name": row.get("name"),
                    "crm_user_id": row.get("crm_user_id"),
                    "crm_alt_user_id": row.get("crm_alt_user_id"),
                    "first_name": row.get("first_name"),
                    "last_name": row.get("last_name"),
                }
                for row in mapped
            ]
            integration.last_user_sync_at = timezone.now()
            integration.save(update_fields=["last_user_sync_at", "updated_at"])
        elif sync_type == IntegrationSyncLog.SYNC_ORDERS:
            mapped = _resolve_order_employee_ids(org, mapped, integration=integration)
            result = process_orders_rows(org, _normalize_order_rows(mapped))
            integration.last_order_sync_at = timezone.now()
            integration.save(update_fields=["last_order_sync_at", "updated_at"])
        else:
            raise ValueError(f"Unsupported sync type: {sync_type}")

        if integration.provider == "salesforce" and integration.credentials.get("access_token"):
            integration.save(update_fields=["credentials", "updated_at"])

        log.result = result
        log.status = IntegrationSyncLog.STATUS_COMPLETED
        log.error_message = ""
    except Exception as exc:
        logger.exception("Integration sync failed: %s", integration.pk)
        log.status = IntegrationSyncLog.STATUS_FAILED
        log.error_message = str(exc)
        log.result = {}
        raise
    finally:
        log.completed_at = timezone.now()
        log.save(
            update_fields=[
                "status",
                "result",
                "error_message",
                "records_fetched",
                "completed_at",
            ]
        )
    return log


def run_webhook_import(integration, sync_type, payload, triggered_by=None):
    """Import users/orders pushed from Zapier, Make, or custom middleware."""
    from .webhook import WebhookConnector

    log = IntegrationSyncLog.objects.create(
        integration=integration,
        sync_type=sync_type,
        status=IntegrationSyncLog.STATUS_RUNNING,
        triggered_by=triggered_by,
    )
    try:
        resource = "users" if "users" in sync_type else "orders"
        section = _section_config(integration, resource)
        raw_records = WebhookConnector.normalize_inbound_payload(
            payload, resource, integration.config or {}
        )
        mapped = map_records(raw_records, section.get("field_map") or {}, section.get("defaults"))
        log.records_fetched = len(mapped)
        org = integration.organization

        if sync_type == IntegrationSyncLog.SYNC_WEBHOOK_USERS:
            result = process_users_rows(org, mapped)
            integration.last_user_sync_at = timezone.now()
            integration.save(update_fields=["last_user_sync_at", "updated_at"])
        else:
            result = process_orders_rows(org, _normalize_order_rows(mapped))
            integration.last_order_sync_at = timezone.now()
            integration.save(update_fields=["last_order_sync_at", "updated_at"])

        log.result = result
        log.status = IntegrationSyncLog.STATUS_COMPLETED
    except Exception as exc:
        log.status = IntegrationSyncLog.STATUS_FAILED
        log.error_message = str(exc)
        log.result = {}
        raise
    finally:
        log.completed_at = timezone.now()
        log.save(
            update_fields=[
                "status",
                "result",
                "error_message",
                "records_fetched",
                "completed_at",
            ]
        )
    return log


def test_integration(integration):
    try:
        connector = get_connector(integration)
    except Exception as exc:
        logger.exception("Failed to initialize connector for integration %s", integration.pk)
        return {"ok": False, "message": str(exc)}
    try:
        connector.test_connection()
        return {"ok": True, "message": "Connection successful"}
    except ConnectorError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:
        logger.exception("Integration test failed for integration %s", integration.pk)
        return {"ok": False, "message": str(exc)}


def run_full_sync(integration, triggered_by=None, limit=None):
    """
    Full CRM workflow: sync users → sync orders (with commission calculation).
    Users must be synced first so CRM owner ids map to Incentra employee ids.
    """
    user_log = run_pull_sync(
        integration,
        IntegrationSyncLog.SYNC_USERS,
        triggered_by=triggered_by,
        limit=limit,
    )
    order_log = run_pull_sync(
        integration,
        IntegrationSyncLog.SYNC_ORDERS,
        triggered_by=triggered_by,
        limit=limit,
    )
    return {
        "users": {
            "log_id": user_log.pk,
            "status": user_log.status,
            "result": user_log.result,
        },
        "orders": {
            "log_id": order_log.pk,
            "status": order_log.status,
            "result": order_log.result,
        },
    }
