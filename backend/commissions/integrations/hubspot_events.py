"""Real-time HubSpot webhook processing for deals and owners."""

import logging

from django.utils import timezone

from ..imports import process_orders_rows
from .user_import import process_users_rows
from ..models import IntegrationSyncLog
from .mapper import map_record, map_records
from .registry import get_connector
from .sync import (
    _apply_order_automation_defaults,
    _normalize_order_rows,
    _resolve_order_employee_ids,
    _section_config,
    _sync_organization,
    build_hubspot_owner_index,
    repair_hubspot_profile_mappings,
)

logger = logging.getLogger("commissions")

DEAL_EVENT_TYPES = {
    "deal.creation",
    "deal.propertyChange",
}


def _deal_stage_allowed(integration, deal_record):
    section = _section_config(integration, "orders")
    allowed = {
        str(stage).strip().lower()
        for stage in (section.get("deal_stages") or ["closedwon"])
    }
    stage = str(deal_record.get("dealstage") or "").strip().lower()
    return stage in allowed


def import_hubspot_deal(integration, deal_id):
    """Fetch one HubSpot deal and import it through the standard order pipeline."""
    connector = get_connector(integration)
    deal = connector.fetch_deal_by_id(deal_id)
    if not deal:
        return {"skipped": True, "reason": f"Deal {deal_id} not found in HubSpot"}

    if not _deal_stage_allowed(integration, deal):
        return {
            "skipped": True,
            "reason": (
                f"Deal {deal_id} stage '{deal.get('dealstage')}' "
                "is not configured for import"
            ),
        }

    section = _section_config(integration, "orders")
    field_map = section.get("field_map") or {}
    defaults = section.get("defaults") or {}
    mapped = [map_record(deal, field_map, defaults=defaults)]
    mapped = _apply_order_automation_defaults(mapped, integration)

    org = _sync_organization(integration)
    owner_index = build_hubspot_owner_index(integration)
    if owner_index:
        repair_hubspot_profile_mappings(org, owner_index)

    mapped, skipped_orders, unresolved_orders = _resolve_order_employee_ids(
        org,
        mapped,
        integration=integration,
        owner_index=owner_index,
    )
    if unresolved_orders:
        return {
            "skipped": True,
            "reason": unresolved_orders[0].get("reason"),
            "unresolved_orders": unresolved_orders,
        }
    if skipped_orders:
        return {
            "skipped": True,
            "reason": skipped_orders[0].get("reason"),
            "skipped_orders": skipped_orders,
        }

    result = process_orders_rows(org, _normalize_order_rows(mapped))
    result["deal_id"] = str(deal_id)
    return result


def import_hubspot_owner(integration, owner_id):
    """Fetch one HubSpot owner and import as an Incentra user."""
    connector = get_connector(integration)
    owner = connector.fetch_owner(owner_id)
    if not owner:
        return {"skipped": True, "reason": f"Owner {owner_id} not found in HubSpot"}

    section = _section_config(integration, "users")
    field_map = section.get("field_map") or {}
    defaults = section.get("defaults") or {}
    mapped = map_records([owner], field_map, defaults=defaults)
    org = _sync_organization(integration)
    return process_users_rows(org, mapped, allow_updates=True)


def process_hubspot_webhook_payload(integration, payload):
    """Handle HubSpot subscription notifications (deal/owner events)."""
    events = payload if isinstance(payload, list) else [payload]
    results = []
    for event in events:
        if not isinstance(event, dict):
            continue
        subscription_type = str(event.get("subscriptionType") or "").strip()
        object_id = event.get("objectId")
        if not object_id:
            continue

        try:
            if subscription_type in DEAL_EVENT_TYPES:
                property_name = str(event.get("propertyName") or "").strip().lower()
                if subscription_type == "deal.propertyChange" and property_name not in (
                    "dealstage",
                    "",
                ):
                    continue
                results.append({
                    "event": subscription_type,
                    "object_id": object_id,
                    "result": import_hubspot_deal(integration, object_id),
                })
            elif subscription_type in {"owner.creation", "contact.creation"}:
                results.append({
                    "event": subscription_type,
                    "object_id": object_id,
                    "result": import_hubspot_owner(integration, object_id),
                })
        except Exception as exc:
            logger.exception(
                "HubSpot webhook event failed integration=%s event=%s",
                integration.pk,
                subscription_type,
            )
            results.append({
                "event": subscription_type,
                "object_id": object_id,
                "error": str(exc),
            })
    return results


def run_hubspot_webhook_import(integration, payload, triggered_by=None):
    log = IntegrationSyncLog.objects.create(
        integration=integration,
        sync_type=IntegrationSyncLog.SYNC_HUBSPOT_WEBHOOK,
        status=IntegrationSyncLog.STATUS_RUNNING,
        triggered_by=triggered_by,
    )
    try:
        results = process_hubspot_webhook_payload(integration, payload)
        log.records_fetched = len(results)
        log.result = {"events": results}
        log.status = IntegrationSyncLog.STATUS_COMPLETED
        integration.last_order_sync_at = timezone.now()
        integration.save(update_fields=["last_order_sync_at", "updated_at"])
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
