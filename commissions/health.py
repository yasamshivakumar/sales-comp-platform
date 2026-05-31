from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    """Liveness probe — process is up."""
    return Response({"status": "ok"})


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
    except Exception:
        db_ok = False

    celery_ok = None
    if settings.CELERY_BROKER_URL:
        try:
            from config.celery import app as celery_app

            celery_ok = celery_app.control.ping(timeout=1.0)
            celery_ok = bool(celery_ok)
        except Exception:
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
