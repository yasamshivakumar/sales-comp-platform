"""API for third-party CRM integrations (Salesforce, REST, webhooks)."""

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .audit import record_audit
from .integrations.registry import DEFAULT_CONFIG, list_providers
from .integrations.sync import (
    ensure_webhook_secret,
    run_full_sync,
    run_pull_sync,
    run_webhook_import,
    test_integration,
)
from .models import ExternalIntegration, IntegrationSyncLog
from .permissions import require_admin
from .serializers import ExternalIntegrationSerializer, IntegrationSyncLogSerializer
from .tenants import filter_queryset_by_organization


def _mask_credentials(credentials):
    if not credentials:
        return {}
    masked = {}
    for key, value in credentials.items():
        if key in ("access_token", "password", "client_secret", "api_key", "security_token"):
            masked[key] = "••••••••" if value else ""
        else:
            masked[key] = value
    return masked


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

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        data = response.data
        data["credentials_masked"] = _mask_credentials(data.get("credentials"))
        if data.get("provider") == ExternalIntegration.PROVIDER_WEBHOOK:
            data["webhook_urls"] = _webhook_urls(request, data.get("webhook_secret"))
        return Response(data)


def _webhook_urls(request, secret):
    if not secret:
        return {}
    base = request.build_absolute_uri("/api/integrations/webhook/").rstrip("/")
    return {
        "users": f"{base}/{secret}/users/",
        "orders": f"{base}/{secret}/orders/",
    }


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


@api_view(["POST"])
@permission_classes([AllowAny])
def integration_webhook_users(request, webhook_secret):
    return _webhook_handler(request, webhook_secret, IntegrationSyncLog.SYNC_WEBHOOK_USERS)


@api_view(["POST"])
@permission_classes([AllowAny])
def integration_webhook_orders(request, webhook_secret):
    return _webhook_handler(request, webhook_secret, IntegrationSyncLog.SYNC_WEBHOOK_ORDERS)


def _webhook_handler(request, webhook_secret, sync_type):
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
