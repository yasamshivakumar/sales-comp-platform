from django.conf import settings
from django.db import DatabaseError, connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    """Landing page when visiting the service root URL (e.g. on Render)."""
    return Response(
        {
            "service": "Incentra API",
            "status": "running",
            "endpoints": {
                "health": "/api/health/",
                "readiness": "/api/health/ready/",
                "login": "/api/auth/email-login/",
                "signup": "/api/auth/signup/",
                "statements": "/api/statements/me/",
                "leaderboard": "/api/leaderboard/",
                "audit_logs": "/api/audit-logs/",
                "territories": "/api/territories/",
                "payout_runs": "/api/payout-runs/",
                "disputes": "/api/disputes/",
                "integrations": "/api/integrations/",
                "integration_webhook": "/api/integrations/webhook/{secret}/users/",
                "api": "/api/",
                "admin": "/admin/",
            },
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness probe — process is up."""
    import os

    return Response({
        "status": "ok",
        "commit": os.getenv("RENDER_GIT_COMMIT", ""),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    """Readiness probe — includes database connectivity."""
    db_ok = False
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except DatabaseError:
        db_ok = False

    celery_ok = None
    if settings.CELERY_BROKER_URL:
        try:
            from config.celery import app as celery_app

            celery_ok = celery_app.control.ping(timeout=1.0)
            celery_ok = bool(celery_ok)
        except (OSError, TimeoutError, ConnectionError, RuntimeError):
            celery_ok = False

    healthy = db_ok and (celery_ok is not False)
    payload = {
        "status": "ok" if healthy else "degraded",
        "database": db_ok,
        "celery": celery_ok,
        "async_imports": bool(settings.CELERY_BROKER_URL),
        "oidc_enabled": settings.OIDC_ENABLED,
    }
    status_code = 200 if healthy else 503
    return Response(payload, status=status_code)
