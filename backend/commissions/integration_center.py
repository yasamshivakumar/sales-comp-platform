"""CRM Integration Center — enterprise APIs over ExternalIntegration."""

from __future__ import annotations

from copy import deepcopy

from django.db.models import Q
from django.utils import timezone

from .audit import record_audit
from .credential_crypto import mask_credentials
from .integrations.registry import DEFAULT_CONFIG, list_providers
from .integrations.sync import (
    ensure_webhook_secret,
    run_full_sync,
    run_pull_sync,
)
from .models import (
    AuditLog,
    CRMFieldMapping,
    CRMIdentityMapping,
    CRMSyncJob,
    ExternalIntegration,
    IntegrationSyncLog,
    Order,
    UserProfile,
)
from .tenants import filter_queryset_by_organization

INCENTRA_USER_TARGETS = [
    {"field": "name", "label": "Employee Name", "required": True},
    {"field": "email", "label": "Email", "required": True},
    {"field": "employee_id", "label": "Employee ID", "required": False},
    {"field": "crm_user_id", "label": "CRM User ID", "required": True},
    {"field": "role", "label": "Role", "required": False},
    {"field": "title", "label": "Title", "required": False},
]

INCENTRA_ORDER_TARGETS = [
    {"field": "order_id", "label": "Order ID", "required": True},
    {"field": "sales_amount", "label": "Sales Amount", "required": True},
    {"field": "order_date", "label": "Order Date", "required": True},
    {"field": "crm_owner_id", "label": "Sales Rep (CRM Owner)", "required": True},
    {"field": "order_status", "label": "Import Status", "required": False},
    {"field": "currency", "label": "Currency", "required": False},
]

PROVIDER_SOURCE_FIELDS = {
    "salesforce": {
        "users": ["Id", "Name", "Email", "Username", "EmployeeNumber", "Title"],
        "deals": [
            "Id",
            "Name",
            "Amount",
            "CloseDate",
            "OwnerId",
            "StageName",
            "CurrencyIsoCode",
        ],
        "accounts": ["Id", "Name"],
        "products": ["Id", "Name", "ProductCode"],
    },
    "hubspot": {
        "users": ["id", "email", "full_name", "first_name", "last_name"],
        "deals": [
            "id",
            "dealname",
            "amount",
            "closedate",
            "hubspot_owner_id",
            "dealstage",
            "currency",
        ],
        "accounts": ["id", "name"],
        "products": ["id", "name"],
    },
}


def _org(request):
    return getattr(request, "organization", None)


def _integrations_qs(request):
    qs = ExternalIntegration.objects.select_related("organization", "created_by")
    return filter_queryset_by_organization(qs, _org(request))


def _freq_to_minutes(freq):
    return {"hourly": 60, "daily": 1440, "realtime": 5}.get(freq or "", 0)


def _apply_frequency(integration, freq):
    integration.sync_frequency = freq or ExternalIntegration.FREQ_MANUAL
    minutes = _freq_to_minutes(integration.sync_frequency)
    if minutes > 0:
        integration.auto_sync_enabled = True
        integration.auto_sync_interval_minutes = minutes
    elif integration.sync_frequency == ExternalIntegration.FREQ_MANUAL:
        integration.auto_sync_enabled = False


def _seed_field_mappings(integration):
    config = integration.config or DEFAULT_CONFIG.get(integration.provider) or {}
    created = 0
    for object_key, source_object in (("users", "users"), ("orders", "deals")):
        section = config.get(object_key) or {}
        for target, source in (section.get("field_map") or {}).items():
            _, was_created = CRMFieldMapping.objects.update_or_create(
                connection=integration,
                source_object=source_object,
                target_field=target,
                defaults={
                    "source_field": str(source),
                    "is_required": target
                    in (
                        "email",
                        "name",
                        "order_id",
                        "sales_amount",
                        "crm_owner_id",
                        "crm_user_id",
                    ),
                },
            )
            if was_created:
                created += 1
    return created


def _mappings_to_field_map(integration, source_object):
    rows = CRMFieldMapping.objects.filter(
        connection=integration, source_object=source_object
    )
    return {row.target_field: row.source_field for row in rows}


def sync_config_from_mappings(integration):
    config = deepcopy(integration.config or DEFAULT_CONFIG.get(integration.provider) or {})
    users_map = _mappings_to_field_map(integration, "users")
    deals_map = _mappings_to_field_map(integration, "deals")
    config.setdefault("users", {})
    config.setdefault("orders", {})
    if users_map:
        config["users"]["field_map"] = users_map
    if deals_map:
        config["orders"]["field_map"] = deals_map
    rules = integration.sync_rules or {}
    if rules.get("import_status"):
        fmap = config.setdefault("orders", {}).setdefault("field_map", {})
        fmap["order_status"] = f"={rules['import_status']}"
    integration.config = config
    integration.save(update_fields=["config", "updated_at"])
    return config


def build_center_catalog():
    providers = [{**p} for p in list_providers()]
    providers.append(
        {
            "id": "dynamics",
            "name": "Microsoft Dynamics",
            "description": "Coming soon — Dynamics 365 Sales integration.",
            "coming_soon": True,
            "supports_pull_users": False,
            "supports_pull_orders": False,
        }
    )
    return {
        "providers": providers,
        "source_fields": PROVIDER_SOURCE_FIELDS,
        "target_fields": {"users": INCENTRA_USER_TARGETS, "deals": INCENTRA_ORDER_TARGETS},
        "default_config": DEFAULT_CONFIG,
    }


def _serialize_job(job):
    return {
        "id": job.id,
        "connection_id": job.connection_id,
        "connection_name": job.connection.name if job.connection_id else "",
        "provider": job.connection.provider if job.connection_id else "",
        "sync_type": job.sync_type,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "records_processed": job.records_processed,
        "failed_records": job.failed_records,
        "error_details": job.error_details or [],
        "result": job.result or {},
    }


def _serialize_connection(integration):
    user_count = 0
    order_count = 0
    last_log = (
        IntegrationSyncLog.objects.filter(integration=integration)
        .order_by("-started_at")
        .first()
    )
    for log in IntegrationSyncLog.objects.filter(
        integration=integration, status=IntegrationSyncLog.STATUS_COMPLETED
    ).order_by("-started_at")[:20]:
        result = log.result or {}
        amt = int(result.get("success") or result.get("created") or log.records_fetched or 0)
        if log.sync_type in (IntegrationSyncLog.SYNC_USERS, IntegrationSyncLog.SYNC_WEBHOOK_USERS):
            user_count += amt
        if log.sync_type in (
            IntegrationSyncLog.SYNC_ORDERS,
            IntegrationSyncLog.SYNC_WEBHOOK_ORDERS,
            IntegrationSyncLog.SYNC_HUBSPOT_WEBHOOK,
        ):
            order_count += amt

    try:
        creds = mask_credentials(integration.get_decrypted_credentials())
    except Exception:
        creds = mask_credentials(integration.credentials)

    status = integration.connection_status
    if not integration.is_active:
        status = ExternalIntegration.STATUS_DISCONNECTED
    elif integration.token_expires_at and integration.token_expires_at < timezone.now():
        status = ExternalIntegration.STATUS_AUTH_EXPIRED

    last = (
        integration.last_sync_at
        or integration.last_auto_sync_at
        or integration.last_order_sync_at
        or integration.last_user_sync_at
    )
    return {
        "id": integration.id,
        "name": integration.name,
        "provider": integration.provider,
        "provider_label": integration.get_provider_display(),
        "status": status,
        "status_label": dict(ExternalIntegration.STATUS_CHOICES).get(status, status),
        "is_active": integration.is_active,
        "sync_frequency": integration.sync_frequency,
        "auth_method": integration.auth_method,
        "connected_org_name": integration.connected_org_name,
        "connected_user_email": integration.connected_user_email
        or (integration.created_by.email if integration.created_by_id else ""),
        "token_expires_at": (
            integration.token_expires_at.isoformat() if integration.token_expires_at else None
        ),
        "last_sync": last.isoformat() if last else None,
        "records": {"users": user_count, "deals": order_count, "orders": order_count},
        "objects_enabled": integration.objects_enabled
        or {"users": True, "deals": True, "accounts": False, "products": False},
        "sync_rules": integration.sync_rules or {},
        "credentials_masked": creds,
        "coming_soon": integration.provider == ExternalIntegration.PROVIDER_DYNAMICS,
        "last_log_status": last_log.status if last_log else None,
        "created_at": integration.created_at.isoformat() if integration.created_at else None,
    }


def build_center_summary(request):
    qs = _integrations_qs(request)
    org = _org(request)
    connected = qs.filter(is_active=True).exclude(
        connection_status=ExternalIntegration.STATUS_DISCONNECTED
    )
    recent_jobs = CRMSyncJob.objects.filter(connection__in=qs).order_by("-created_at")[:20]
    failed = CRMSyncJob.objects.filter(
        connection__in=qs, status=CRMSyncJob.STATUS_FAILED
    ).count() + IntegrationSyncLog.objects.filter(
        integration__in=qs, status=IntegrationSyncLog.STATUS_FAILED
    ).count()
    users_imported = (
        UserProfile.objects.filter(organization=org)
        .exclude(Q(crm_user_id="") | Q(crm_user_id__isnull=True))
        .count()
    )
    orders_imported = (
        Order.objects.filter(organization=org)
        .exclude(Q(crm_provider="") | Q(crm_provider__isnull=True))
        .count()
    )
    last_sync = None
    for row in qs.order_by("-last_sync_at", "-updated_at"):
        last_sync = (
            row.last_sync_at
            or row.last_auto_sync_at
            or row.last_order_sync_at
            or row.last_user_sync_at
        )
        if last_sync:
            break
    return {
        "kpis": {
            "connected_apps": connected.count(),
            "last_sync": last_sync.isoformat() if last_sync else None,
            "records_imported": users_imported + orders_imported,
            "users_imported": users_imported,
            "orders_imported": orders_imported,
            "sync_errors": failed,
        },
        "connections": [_serialize_connection(i) for i in qs],
        "recent_jobs": [_serialize_job(j) for j in recent_jobs],
    }


def create_connection_from_wizard(request, data):
    org = _org(request)
    provider = (data.get("provider") or "").strip()
    if provider == ExternalIntegration.PROVIDER_DYNAMICS:
        return None, {"error": "Microsoft Dynamics is coming soon."}
    valid = {c[0] for c in ExternalIntegration.PROVIDER_CHOICES}
    if provider not in valid:
        return None, {"error": "Invalid provider"}

    name = (data.get("name") or f"{provider.title()} Connection").strip()
    credentials = data.get("credentials") or {}
    integration = ExternalIntegration(
        organization=org,
        name=name,
        provider=provider,
        is_active=True,
        connection_status=ExternalIntegration.STATUS_CONNECTED,
        auth_method=data.get("auth_method") or ExternalIntegration.AUTH_TOKEN,
        objects_enabled=data.get("objects_enabled")
        or {"users": True, "deals": True, "accounts": False, "products": False},
        sync_rules=data.get("sync_rules")
        or {
            "closed_won_only": True,
            "import_status": "Booked",
            "commission_after_approval": True,
        },
        config=data.get("config") or deepcopy(DEFAULT_CONFIG.get(provider) or {}),
        connected_org_name=(data.get("connected_org_name") or "").strip(),
        connected_user_email=(
            data.get("connected_user_email") or request.user.email or ""
        ).strip(),
        created_by=request.user,
    )
    _apply_frequency(integration, data.get("sync_frequency") or ExternalIntegration.FREQ_DAILY)
    integration.set_encrypted_credentials(credentials)
    integration.save()

    if provider in (
        ExternalIntegration.PROVIDER_WEBHOOK,
        ExternalIntegration.PROVIDER_HUBSPOT,
    ):
        ensure_webhook_secret(integration)

    mappings = data.get("field_mappings") or []
    if mappings:
        for row in mappings:
            CRMFieldMapping.objects.update_or_create(
                connection=integration,
                source_object=row.get("source_object") or "users",
                target_field=row["target_field"],
                defaults={
                    "source_field": row.get("source_field") or "",
                    "is_required": bool(row.get("is_required")),
                },
            )
    else:
        _seed_field_mappings(integration)
    sync_config_from_mappings(integration)

    record_audit(
        request,
        "integration_created",
        {"id": integration.pk, "provider": provider, "via": "wizard"},
    )
    record_audit(
        request,
        "crm_connected",
        {
            "provider": provider,
            "connection_id": integration.pk,
            "message": f"{integration.get_provider_display()} connected by {request.user.email}",
        },
    )
    return integration, None


def list_field_mappings(integration):
    return [
        {
            "id": m.id,
            "source_object": m.source_object,
            "source_field": m.source_field,
            "target_field": m.target_field,
            "is_required": m.is_required,
        }
        for m in CRMFieldMapping.objects.filter(connection=integration)
    ]


def validate_mappings(integration):
    errors = []
    users = {
        m.target_field: m
        for m in CRMFieldMapping.objects.filter(connection=integration, source_object="users")
    }
    deals = {
        m.target_field: m
        for m in CRMFieldMapping.objects.filter(connection=integration, source_object="deals")
    }
    for spec in INCENTRA_USER_TARGETS:
        if spec["required"] and (
            spec["field"] not in users or not (users[spec["field"]].source_field or "").strip()
        ):
            errors.append(
                {
                    "object": "users",
                    "field": spec["field"],
                    "message": f"Required mapping missing: {spec['label']}",
                }
            )
    for spec in INCENTRA_ORDER_TARGETS:
        if (integration.objects_enabled or {}).get("deals", True) and spec["required"] and (
            spec["field"] not in deals or not (deals[spec["field"]].source_field or "").strip()
        ):
            errors.append(
                {
                    "object": "deals",
                    "field": spec["field"],
                    "message": f"Required mapping missing: {spec['label']}",
                }
            )
    return {"ok": len(errors) == 0, "errors": errors}


def update_field_mappings(request, connection_id, mappings):
    integration = _integrations_qs(request).filter(id=connection_id).first()
    if not integration:
        return None, {"error": "Connection not found"}
    seen = set()
    for row in mappings:
        target = (row.get("target_field") or "").strip()
        source_object = (row.get("source_object") or "users").strip()
        if not target:
            continue
        CRMFieldMapping.objects.update_or_create(
            connection=integration,
            source_object=source_object,
            target_field=target,
            defaults={
                "source_field": (row.get("source_field") or "").strip(),
                "is_required": bool(row.get("is_required")),
            },
        )
        seen.add((source_object, target))
    objects = {m.get("source_object") or "users" for m in mappings}
    for obj in objects:
        for existing in CRMFieldMapping.objects.filter(
            connection=integration, source_object=obj
        ):
            if (existing.source_object, existing.target_field) not in seen:
                existing.delete()
    sync_config_from_mappings(integration)
    record_audit(
        request,
        "field_mapping_updated",
        {"connection_id": integration.pk, "provider": integration.provider},
    )
    return {"mappings": list_field_mappings(integration), "validation": validate_mappings(integration)}, None


def preview_records(request, connection_id, resource="deals", limit=10):
    integration = _integrations_qs(request).filter(id=connection_id).first()
    if not integration:
        return None, {"error": "Connection not found"}
    sync_config_from_mappings(integration)
    from .integrations.registry import get_connector

    try:
        connector = get_connector(integration)
        resource_type = "orders" if resource in ("deals", "orders") else "users"
        records = connector.fetch_records(resource_type, limit=limit) or []
    except Exception as exc:
        return None, {"error": str(exc)}

    preview = []
    for row in records[:limit]:
        if not isinstance(row, dict):
            continue
        if resource_type == "orders":
            preview.append(
                {
                    "opportunity_id": row.get("Id") or row.get("id") or row.get("order_id"),
                    "amount": row.get("Amount") or row.get("amount") or row.get("sales_amount"),
                    "owner": row.get("OwnerId")
                    or row.get("hubspot_owner_id")
                    or row.get("crm_owner_id"),
                    "close_date": row.get("CloseDate")
                    or row.get("closedate")
                    or row.get("order_date"),
                    "status": row.get("StageName")
                    or row.get("dealstage")
                    or row.get("order_status"),
                    "name": row.get("Name") or row.get("dealname"),
                }
            )
        else:
            preview.append(
                {
                    "id": row.get("Id") or row.get("id") or row.get("crm_user_id"),
                    "name": row.get("Name") or row.get("full_name") or row.get("name"),
                    "email": row.get("Email") or row.get("email"),
                    "employee_number": row.get("EmployeeNumber") or row.get("employee_id"),
                }
            )
    return {
        "resource": resource,
        "count": len(preview),
        "estimated_total": len(records),
        "records": preview,
    }, None


def _refresh_identity_mappings(integration):
    org = integration.organization
    profiles = UserProfile.objects.filter(organization=org).exclude(
        Q(crm_user_id="") | Q(crm_user_id__isnull=True)
    )
    for p in profiles[:2000]:
        CRMIdentityMapping.objects.update_or_create(
            organization=org,
            crm_provider=integration.provider,
            crm_user_id=p.crm_user_id,
            defaults={
                "connection": integration,
                "employee_id": p.employee_id or "",
                "employee_email": p.email or "",
                "profile": p,
            },
        )


def run_center_sync(request, connection_id, sync_type="full"):
    integration = _integrations_qs(request).filter(id=connection_id).first()
    if not integration:
        return None, {"error": "Connection not found"}
    if integration.provider == ExternalIntegration.PROVIDER_DYNAMICS:
        return None, {"error": "Microsoft Dynamics is coming soon."}

    sync_config_from_mappings(integration)
    job = CRMSyncJob.objects.create(
        connection=integration,
        sync_type=sync_type,
        status=CRMSyncJob.STATUS_RUNNING,
        started_at=timezone.now(),
        triggered_by=request.user,
    )
    integration.connection_status = ExternalIntegration.STATUS_SYNCING
    integration.save(update_fields=["connection_status", "updated_at"])

    try:
        if sync_type == "users":
            result = run_pull_sync(integration, "users", triggered_by=request.user)
        elif sync_type in ("orders", "deals"):
            result = run_pull_sync(integration, "orders", triggered_by=request.user)
        else:
            result = run_full_sync(integration, triggered_by=request.user)

        if isinstance(result, dict) and "users" in result:
            users_r = result.get("users") or {}
            orders_r = result.get("orders") or {}
            processed = int(users_r.get("success") or 0) + int(orders_r.get("success") or 0)
            failed = int(users_r.get("failed") or 0) + int(orders_r.get("failed") or 0)
            errors = (users_r.get("errors") or []) + (orders_r.get("errors") or [])
            payload = result
        else:
            processed = int(
                (result or {}).get("success") or (result or {}).get("records_fetched") or 0
            )
            failed = int((result or {}).get("failed") or 0)
            errors = (result or {}).get("errors") or []
            payload = result or {}

        job.records_processed = processed
        job.failed_records = failed
        job.error_details = errors[:50] if isinstance(errors, list) else []
        job.result = payload
        if failed and processed:
            job.status = CRMSyncJob.STATUS_PARTIAL
        elif failed and not processed:
            job.status = CRMSyncJob.STATUS_FAILED
        else:
            job.status = CRMSyncJob.STATUS_COMPLETED
        job.completed_at = timezone.now()
        job.save()

        integration.connection_status = ExternalIntegration.STATUS_CONNECTED
        integration.last_sync_at = timezone.now()
        integration.save(update_fields=["connection_status", "last_sync_at", "updated_at"])
        _refresh_identity_mappings(integration)
        record_audit(
            request,
            "integration_sync_full" if sync_type == "full" else f"integration_sync_{sync_type}",
            {
                "connection_id": integration.pk,
                "job_id": job.pk,
                "processed": processed,
                "failed": failed,
                "message": f"User sync completed" if sync_type == "users" else "Sync completed",
            },
        )
        return {"job": _serialize_job(job), "result": payload}, None
    except Exception as exc:
        job.status = CRMSyncJob.STATUS_FAILED
        job.failed_records = 1
        job.error_details = [str(exc)]
        job.completed_at = timezone.now()
        job.save()
        integration.connection_status = ExternalIntegration.STATUS_FAILED
        integration.save(update_fields=["connection_status", "updated_at"])
        return None, {"error": str(exc), "job": _serialize_job(job)}


def disconnect_connection(request, connection_id):
    integration = _integrations_qs(request).filter(id=connection_id).first()
    if not integration:
        return None, {"error": "Connection not found"}
    integration.is_active = False
    integration.connection_status = ExternalIntegration.STATUS_DISCONNECTED
    integration.save(update_fields=["is_active", "connection_status", "updated_at"])
    record_audit(
        request,
        "integration_disconnected",
        {"connection_id": integration.pk, "provider": integration.provider},
    )
    return {"ok": True}, None


def list_sync_activity(request, connection_id=None):
    qs = CRMSyncJob.objects.select_related("connection").filter(
        connection__in=_integrations_qs(request)
    )
    if connection_id:
        qs = qs.filter(connection_id=connection_id)
    jobs = [_serialize_job(j) for j in qs.order_by("-created_at")[:100]]

    logs = []
    log_qs = IntegrationSyncLog.objects.filter(integration__in=_integrations_qs(request))
    if connection_id:
        log_qs = log_qs.filter(integration_id=connection_id)
    for log in log_qs.order_by("-started_at")[:50]:
        result = log.result or {}
        logs.append(
            {
                "id": f"log-{log.id}",
                "connection_id": log.integration_id,
                "connection_name": log.integration.name,
                "provider": log.integration.provider,
                "sync_type": log.sync_type,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "records_processed": log.records_fetched or int(result.get("success") or 0),
                "failed_records": int(result.get("failed") or 0),
                "error_details": result.get("errors")
                or ([log.error_message] if log.error_message else []),
                "result": result,
            }
        )

    audit = []
    org = _org(request)
    for row in (
        AuditLog.objects.filter(organization=org)
        .filter(
            Q(action__startswith="integration")
            | Q(action__startswith="crm_")
            | Q(action="field_mapping_updated")
        )
        .order_by("-created_at")[:80]
    ):
        audit.append(
            {
                "id": row.id,
                "action": row.action,
                "user_email": row.user_email,
                "detail": row.detail or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "message": (row.detail or {}).get("message")
                or f"{row.action.replace('_', ' ')} by {row.user_email or 'system'}",
            }
        )
    return {"jobs": jobs, "logs": logs, "audit": audit}


def list_identity_mappings(request, connection_id=None):
    qs = CRMIdentityMapping.objects.filter(organization=_org(request))
    if connection_id:
        qs = qs.filter(connection_id=connection_id)
    return [
        {
            "id": m.id,
            "crm_provider": m.crm_provider,
            "crm_user_id": m.crm_user_id,
            "employee_id": m.employee_id,
            "employee_email": m.employee_email,
            "connection_id": m.connection_id,
        }
        for m in qs.order_by("crm_provider", "crm_user_id")[:500]
    ]


def upsert_identity_mapping(request, data):
    org = _org(request)
    crm_user_id = (data.get("crm_user_id") or "").strip()
    employee_id = (data.get("employee_id") or "").strip()
    provider = (data.get("crm_provider") or "").strip()
    if not crm_user_id or not employee_id or not provider:
        return None, {"error": "crm_provider, crm_user_id, and employee_id are required"}
    profile = UserProfile.objects.filter(organization=org, employee_id=employee_id).first()
    connection = None
    if data.get("connection_id"):
        connection = _integrations_qs(request).filter(id=data["connection_id"]).first()
    obj, _ = CRMIdentityMapping.objects.update_or_create(
        organization=org,
        crm_provider=provider,
        crm_user_id=crm_user_id,
        defaults={
            "employee_id": employee_id,
            "employee_email": (profile.email if profile else data.get("employee_email") or ""),
            "profile": profile,
            "connection": connection,
        },
    )
    if profile and not profile.crm_user_id:
        profile.crm_user_id = crm_user_id
        profile.save(update_fields=["crm_user_id"])
    record_audit(
        request,
        "crm_identity_mapped",
        {
            "crm_provider": provider,
            "crm_user_id": crm_user_id,
            "employee_id": employee_id,
        },
    )
    return {
        "id": obj.id,
        "crm_provider": obj.crm_provider,
        "crm_user_id": obj.crm_user_id,
        "employee_id": obj.employee_id,
        "employee_email": obj.employee_email,
    }, None


def retry_failed_job(request, job_id):
    job = (
        CRMSyncJob.objects.select_related("connection")
        .filter(id=job_id, connection__in=_integrations_qs(request))
        .first()
    )
    if not job:
        return None, {"error": "Sync job not found"}
    return run_center_sync(request, job.connection_id, sync_type=job.sync_type)
