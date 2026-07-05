"""Run pull/push sync jobs for external integrations."""

import logging
import secrets

from django.utils import timezone

from ..models import ExternalIntegration, IntegrationSyncLog
from .base import ConnectorError
from .employee_ids import (
    build_hubspot_owner_index,
    normalize_crm_id,
    repair_hubspot_profile_mappings,
    resolve_crm_user_to_employee_id,
    resolve_error_hint,
    resolve_remap_target,
    _lookup_owner_meta,
)
from .order_sync import process_orders_rows
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


def _apply_order_automation_defaults(rows, integration):
    """Apply CRM automation flags (e.g. auto-mark closed-won deals as Success)."""
    section = _section_config(integration, "orders")
    auto_success = section.get(
        "auto_mark_success",
        integration.provider == ExternalIntegration.PROVIDER_HUBSPOT,
    )
    if not auto_success:
        return rows
    updated = []
    for row in rows:
        item = dict(row)
        item["order_status"] = "Success"
        updated.append(item)
    return updated


def _sync_organization(integration):
    org = integration.organization
    if not org:
        raise ValueError(
            "Integration has no organization assigned. "
            "Set organization on the integration before syncing."
        )
    return org


def _resolve_order_employee_ids(organization, rows, integration=None, owner_index=None):
    """Map CRM owner ids from deals to Incentra employee_id before order import."""
    section = _section_config(integration, "orders") if integration else {}
    skip_archived = section.get("skip_archived_owners", True)
    remap = section.get("archived_owner_remap") or {}
    auto_import = section.get(
        "auto_import_owners",
        bool(integration and integration.provider == ExternalIntegration.PROVIDER_HUBSPOT),
    )

    resolved = []
    skipped = []
    unresolved = []
    for row in rows:
        item = dict(row)
        if str(item.get("employee_id", "")).strip():
            resolved.append(item)
            continue

        crm_owner_id = (
            item.get("crm_owner_id")
            or item.get("hubspot_owner_id")
            or item.get("crm_user_id")
        )
        if not str(crm_owner_id or "").strip():
            unresolved.append({
                "order_id": item.get("order_id") or item.get("id"),
                "reason": (
                    "No employee_id or CRM owner id on order row. "
                    "Map crm_owner_id in integration config or include employee_id."
                ),
            })
            continue

        owner_id = normalize_crm_id(crm_owner_id)
        remap_target = remap.get(str(crm_owner_id)) or remap.get(owner_id)
        if remap_target:
            employee_id = resolve_remap_target(
                organization,
                remap_target,
                integration=integration,
                owner_index=owner_index,
            )
            if employee_id:
                item["employee_id"] = employee_id
                resolved.append(item)
                continue

        owner_meta = _lookup_owner_meta(owner_id, integration, owner_index)
        if owner_meta and owner_meta.get("archived") and skip_archived:
            skipped.append({
                "order_id": item.get("order_id") or item.get("id"),
                "crm_owner_id": owner_id,
                "owner_email": owner_meta.get("email"),
                "reason": (
                    "Deal owner removed/archived in HubSpot; skipped. "
                    "Reassign in HubSpot or set archived_owner_remap."
                ),
            })
            continue

        employee_id = resolve_crm_user_to_employee_id(
            organization,
            crm_owner_id,
            integration=integration,
            owner_index=owner_index,
            auto_import=auto_import,
            match_archived_owners=False,
        )
        if not employee_id:
            hint = resolve_error_hint(crm_owner_id, integration, owner_index)
            unresolved.append({
                "order_id": item.get("order_id") or item.get("id"),
                "crm_owner_id": crm_owner_id,
                "reason": (
                    f"No Incentra employee mapped for CRM owner id {crm_owner_id}."
                    f"{hint}"
                ),
            })
            continue
        item["employee_id"] = employee_id
        resolved.append(item)
    return resolved, skipped, unresolved


def _incremental_since(integration, sync_type):
    """Return datetime watermark for incremental CRM order/user pulls."""
    section = _section_config(integration, sync_type)
    if section.get("incremental_sync", True) is False:
        return None
    if sync_type == IntegrationSyncLog.SYNC_ORDERS:
        return integration.last_order_sync_at
    if sync_type == IntegrationSyncLog.SYNC_USERS:
        return integration.last_user_sync_at
    return None


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

        since = _incremental_since(integration, sync_type)
        raw_records = connector.fetch_records(sync_type, limit=limit, since=since)
        mapped = map_records(raw_records, field_map, defaults=defaults)
        if sync_type == IntegrationSyncLog.SYNC_ORDERS:
            mapped = _apply_order_automation_defaults(mapped, integration)
        log.records_fetched = len(mapped)

        org = _sync_organization(integration)
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
            owner_index = (
                build_hubspot_owner_index(integration)
                if integration.provider == "hubspot"
                else None
            )
            if owner_index:
                repair_hubspot_profile_mappings(org, owner_index)
            mapped, skipped_orders, unresolved_orders = _resolve_order_employee_ids(
                org,
                mapped,
                integration=integration,
                owner_index=owner_index,
            )
            result = process_orders_rows(
                org,
                _normalize_order_rows(mapped),
                crm_provider=integration.provider,
                integration=integration,
            )
            if skipped_orders:
                result["skipped_orders"] = skipped_orders
                result["skipped"] = len(skipped_orders)
            if unresolved_orders:
                result["unresolved_orders"] = unresolved_orders
                result["failed"] = result.get("failed", 0) + len(unresolved_orders)
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
        org = _sync_organization(integration)

        if sync_type == IntegrationSyncLog.SYNC_WEBHOOK_USERS:
            result = process_users_rows(org, mapped)
            integration.last_user_sync_at = timezone.now()
            integration.save(update_fields=["last_user_sync_at", "updated_at"])
        else:
            mapped, skipped_orders, unresolved_orders = _resolve_order_employee_ids(
                org,
                mapped,
                integration=integration,
            )
            mapped = _apply_order_automation_defaults(mapped, integration)
            result = process_orders_rows(
                org,
                _normalize_order_rows(mapped),
                crm_provider=integration.provider,
                integration=integration,
            )
            if skipped_orders:
                result["skipped_orders"] = skipped_orders
                result["skipped"] = len(skipped_orders)
            if unresolved_orders:
                result["unresolved_orders"] = unresolved_orders
                result["failed"] = result.get("failed", 0) + len(unresolved_orders)
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


def run_auto_sync_for_integration(integration, *, triggered_by=None, limit=None):
    """Run a full CRM sync for one integration and stamp last_auto_sync_at."""
    if integration.provider == ExternalIntegration.PROVIDER_WEBHOOK:
        return {"skipped": True, "reason": "Webhook integrations use inbound POST only."}
    if not integration.is_active:
        return {"skipped": True, "reason": "Integration is inactive."}

    log = IntegrationSyncLog.objects.create(
        integration=integration,
        sync_type=IntegrationSyncLog.SYNC_AUTO,
        status=IntegrationSyncLog.STATUS_RUNNING,
        triggered_by=triggered_by,
    )
    result = {}
    try:
        result = run_full_sync(integration, triggered_by=triggered_by, limit=limit)
        integration.last_auto_sync_at = timezone.now()
        integration.save(update_fields=["last_auto_sync_at", "updated_at"])
        log.result = result
        log.status = IntegrationSyncLog.STATUS_COMPLETED
        log.records_fetched = (
            (result.get("users", {}).get("result") or {}).get("success", 0)
            + (result.get("orders", {}).get("result") or {}).get("success", 0)
        )
    except Exception as exc:
        logger.exception("Auto sync failed for integration %s", integration.pk)
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
    return {"log_id": log.pk, "result": result}


def run_due_auto_integration_syncs():
    """Queue or run automatic sync for integrations that are due."""
    from datetime import timedelta

    now = timezone.now()
    due_ids = []
    for integration in ExternalIntegration.objects.filter(
        is_active=True,
        auto_sync_enabled=True,
    ).exclude(provider=ExternalIntegration.PROVIDER_WEBHOOK):
        interval = max(int(integration.auto_sync_interval_minutes or 15), 5)
        last = integration.last_auto_sync_at
        if not last or (now - last) >= timedelta(minutes=interval):
            due_ids.append(integration.pk)

    queued = []
    for integration_id in due_ids:
        try:
            from ..tasks import run_auto_sync_for_integration_task

            run_auto_sync_for_integration_task.delay(integration_id)
            queued.append(integration_id)
        except Exception:
            integration = ExternalIntegration.objects.get(pk=integration_id)
            run_auto_sync_for_integration(integration)
            queued.append(integration_id)
    return {"queued": queued, "count": len(queued)}
