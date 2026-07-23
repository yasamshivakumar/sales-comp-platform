"""API for third-party CRM integrations (Salesforce, REST, webhooks)."""

from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .audit import record_audit
from .integrations.registry import DEFAULT_CONFIG, list_providers
from .integrations.sync import (
    ensure_webhook_secret,
    run_auto_sync_for_integration,
    run_full_sync,
    run_pull_sync,
    run_webhook_import,
    test_integration,
)
from .integrations.hubspot_events import run_hubspot_webhook_import
from .models import ExternalIntegration, IntegrationSyncLog, UserProfile
from .permissions import require_admin
from .serializers import ExternalIntegrationSerializer, IntegrationSyncLogSerializer, UserProfileSerializer
from .tenants import filter_queryset_by_organization


def _webhook_secret_is_valid(raw_secret):
    secret = (raw_secret or "").strip()
    min_len = int(getattr(settings, "WEBHOOK_SECRET_MIN_LENGTH", 24))
    return bool(secret) and len(secret) >= min_len


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_providers(request):
    require_admin(request)
    return Response({"providers": list_providers(), "default_config": DEFAULT_CONFIG})


class ExternalIntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = ExternalIntegrationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        require_admin(self.request)
        qs = ExternalIntegration.objects.select_related("organization", "created_by")
        return filter_queryset_by_organization(
            qs, getattr(self.request, "organization", None)
        )

    def perform_create(self, serializer):
        require_admin(self.request)
        org = getattr(self.request, "organization", None)
        provider = serializer.validated_data.get("provider")
        config = serializer.validated_data.get("config") or {}
        if not config and provider in DEFAULT_CONFIG:
            config = DEFAULT_CONFIG[provider]
        instance = serializer.save(
            organization=org,
            created_by=self.request.user,
            config=config,
        )
        if instance.provider == ExternalIntegration.PROVIDER_WEBHOOK:
            ensure_webhook_secret(instance)
        elif instance.provider == ExternalIntegration.PROVIDER_HUBSPOT:
            ensure_webhook_secret(instance)
        elif not instance.webhook_secret:
            instance.webhook_secret = None
            instance.save(update_fields=["webhook_secret"])
        record_audit(
            self.request,
            "integration_created",
            {"id": instance.pk, "provider": instance.provider},
        )

    def perform_update(self, serializer):
        require_admin(self.request)
        instance = serializer.save()
        if instance.provider == ExternalIntegration.PROVIDER_WEBHOOK and not instance.webhook_secret:
            ensure_webhook_secret(instance)
        elif instance.webhook_secret == "":
            instance.webhook_secret = None
            instance.save(update_fields=["webhook_secret"])
        record_audit(self.request, "integration_updated", {"id": instance.pk})

    def perform_destroy(self, instance):
        require_admin(self.request)
        record_audit(
            self.request,
            "integration_deleted",
            {"id": instance.pk, "name": instance.name},
        )
        instance.delete()

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_integration_connection(request, integration_id):
    require_admin(request)
    org = getattr(request, "organization", None)
    integration = ExternalIntegration.objects.filter(
        pk=integration_id,
        organization=org,
    ).first()
    if not integration:
        return Response({"error": "Integration not found"}, status=404)
    try:
        result = test_integration(integration)
    except Exception as exc:
        return Response({"ok": False, "error": str(exc), "message": str(exc)}, status=400)
    if not result.get("ok"):
        result["error"] = result.get("message") or "Connection failed"
    return Response(result, status=200 if result.get("ok") else 400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_integration_users(request, integration_id):
    require_admin(request)
    return _run_sync(request, integration_id, IntegrationSyncLog.SYNC_USERS)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_integration_orders(request, integration_id):
    require_admin(request)
    return _run_sync(request, integration_id, IntegrationSyncLog.SYNC_ORDERS)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_integration_full(request, integration_id):
    """Users → orders → commissions in one workflow."""
    require_admin(request)
    org = getattr(request, "organization", None)
    integration = ExternalIntegration.objects.filter(
        pk=integration_id,
        organization=org,
        is_active=True,
    ).first()
    if not integration:
        return Response({"error": "Integration not found or inactive"}, status=404)
    if integration.provider == ExternalIntegration.PROVIDER_WEBHOOK:
        return Response(
            {"error": "Webhook integrations receive data via POST; use webhook URLs."},
            status=400,
        )
    limit = request.data.get("limit")
    try:
        result = run_full_sync(integration, triggered_by=request.user, limit=limit)
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)
    record_audit(
        request,
        "integration_sync_full",
        {"integration_id": integration.pk, "result": result},
    )
    return Response(result)


def _run_sync(request, integration_id, sync_type):
    org = getattr(request, "organization", None)
    integration = ExternalIntegration.objects.filter(
        pk=integration_id,
        organization=org,
        is_active=True,
    ).first()
    if not integration:
        return Response({"error": "Integration not found or inactive"}, status=404)
    if integration.provider == ExternalIntegration.PROVIDER_WEBHOOK:
        return Response(
            {"error": "Webhook integrations receive data via POST; use webhook URLs."},
            status=400,
        )
    limit = request.data.get("limit")
    try:
        log = run_pull_sync(integration, sync_type, triggered_by=request.user, limit=limit)
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)
    record_audit(
        request,
        f"integration_sync_{sync_type}",
        {"integration_id": integration.pk, "log_id": log.pk, "result": log.result},
    )
    return Response(IntegrationSyncLogSerializer(log).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_sync_logs(request, integration_id):
    require_admin(request)
    org = getattr(request, "organization", None)
    integration = ExternalIntegration.objects.filter(
        pk=integration_id,
        organization=org,
    ).first()
    if not integration:
        return Response({"error": "Integration not found"}, status=404)
    logs = integration.sync_logs.all()[:50]
    return Response(IntegrationSyncLogSerializer(logs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_synced_users(request, integration_id):
    """CRM-linked employees imported or updated via integrations."""
    require_admin(request)
    org = getattr(request, "organization", None)
    integration = ExternalIntegration.objects.filter(
        pk=integration_id,
        organization=org,
    ).first()
    if not integration:
        return Response({"error": "Integration not found"}, status=404)
    profiles = (
        UserProfile.objects.filter(organization=org)
        .exclude(crm_user_id="")
        .order_by("name", "email")
    )
    return Response({
        "count": profiles.count(),
        "users": UserProfileSerializer(profiles, many=True).data,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def integration_webhook_users(request, webhook_secret):
    return _webhook_handler(request, webhook_secret, IntegrationSyncLog.SYNC_WEBHOOK_USERS)


integration_webhook_users.throttle_scope = "webhook"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def integration_webhook_orders(request, webhook_secret):
    return _webhook_handler(request, webhook_secret, IntegrationSyncLog.SYNC_WEBHOOK_ORDERS)


integration_webhook_orders.throttle_scope = "webhook"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def integration_hubspot_webhook(request, webhook_secret):
    if not _webhook_secret_is_valid(webhook_secret):
        return Response({"error": "Invalid webhook secret"}, status=404)
    integration = ExternalIntegration.objects.filter(
        webhook_secret=webhook_secret,
        is_active=True,
        provider=ExternalIntegration.PROVIDER_HUBSPOT,
    ).first()
    if not integration:
        return Response({"error": "Invalid webhook secret"}, status=404)
    try:
        log = run_hubspot_webhook_import(integration, request.data)
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)
    return Response({
        "message": "HubSpot event processed",
        "log_id": log.pk,
        "result": log.result,
    })


integration_hubspot_webhook.throttle_scope = "webhook"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trigger_auto_sync(request, integration_id):
    """Manually trigger one automatic full sync (admin)."""
    require_admin(request)
    org = getattr(request, "organization", None)
    integration = ExternalIntegration.objects.filter(
        pk=integration_id,
        organization=org,
        is_active=True,
    ).first()
    if not integration:
        return Response({"error": "Integration not found or inactive"}, status=404)
    try:
        result = run_auto_sync_for_integration(integration, triggered_by=request.user)
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)
    return Response(result)


def _webhook_handler(request, webhook_secret, sync_type):
    if not _webhook_secret_is_valid(webhook_secret):
        return Response({"error": "Invalid webhook secret"}, status=404)
    integration = ExternalIntegration.objects.filter(
        webhook_secret=webhook_secret,
        is_active=True,
        provider=ExternalIntegration.PROVIDER_WEBHOOK,
    ).first()
    if not integration:
        return Response({"error": "Invalid webhook secret"}, status=404)
    try:
        log = run_webhook_import(integration, sync_type, request.data)
    except Exception as exc:
        return Response({"error": str(exc)}, status=400)
    return Response({
        "message": "Import completed",
        "log_id": log.pk,
        "result": log.result,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_center_catalog(request):
    require_admin(request)
    from .integration_center import build_center_catalog

    return Response(build_center_catalog())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_center_summary(request):
    require_admin(request)
    from .integration_center import build_center_summary

    return Response(build_center_summary(request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def integration_center_wizard(request):
    require_admin(request)
    from .integration_center import create_connection_from_wizard, _serialize_connection

    integration, err = create_connection_from_wizard(request, request.data or {})
    if err:
        return Response(err, status=400)
    return Response(_serialize_connection(integration), status=201)


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def integration_center_mappings(request, connection_id):
    require_admin(request)
    from .integration_center import (
        _integrations_qs,
        list_field_mappings,
        update_field_mappings,
        validate_mappings,
    )

    integration = _integrations_qs(request).filter(id=connection_id).first()
    if not integration:
        return Response({"error": "Connection not found"}, status=404)
    if request.method == "GET":
        return Response(
            {
                "mappings": list_field_mappings(integration),
                "validation": validate_mappings(integration),
            }
        )
    data, err = update_field_mappings(
        request, connection_id, request.data.get("mappings") or request.data or []
    )
    if err:
        return Response(err, status=400)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_center_preview(request, connection_id):
    require_admin(request)
    from .integration_center import preview_records

    resource = request.query_params.get("resource") or "deals"
    try:
        limit = int(request.query_params.get("limit") or 10)
    except ValueError:
        limit = 10
    data, err = preview_records(request, connection_id, resource=resource, limit=limit)
    if err:
        return Response(err, status=400)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def integration_center_sync(request, connection_id):
    require_admin(request)
    from .integration_center import run_center_sync

    sync_type = (request.data or {}).get("sync_type") or "full"
    data, err = run_center_sync(request, connection_id, sync_type=sync_type)
    if err:
        return Response(err, status=400)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def integration_center_disconnect(request, connection_id):
    require_admin(request)
    from .integration_center import disconnect_connection

    data, err = disconnect_connection(request, connection_id)
    if err:
        return Response(err, status=404)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_center_activity(request):
    require_admin(request)
    from .integration_center import list_sync_activity

    connection_id = request.query_params.get("connection_id")
    return Response(list_sync_activity(request, connection_id=connection_id))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def integration_center_identities(request):
    require_admin(request)
    from .integration_center import list_identity_mappings, upsert_identity_mapping

    if request.method == "GET":
        connection_id = request.query_params.get("connection_id")
        return Response({"results": list_identity_mappings(request, connection_id)})
    data, err = upsert_identity_mapping(request, request.data or {})
    if err:
        return Response(err, status=400)
    return Response(data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def integration_center_retry_job(request, job_id):
    require_admin(request)
    from .integration_center import retry_failed_job

    data, err = retry_failed_job(request, job_id)
    if err:
        return Response(err, status=400)
    return Response(data)
