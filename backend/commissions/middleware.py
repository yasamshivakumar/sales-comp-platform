import logging
import os
import traceback
import uuid

from django.http import JsonResponse

from .tenants import resolve_request_organization

logger = logging.getLogger("commissions")


class LivenessMiddleware:
    """Answer /ping before any other middleware (DB, sessions, security)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip("/") == "/ping":
            return JsonResponse({
                "status": "ok",
                "commit": os.getenv("RENDER_GIT_COMMIT", ""),
                "service": os.getenv("RENDER_SERVICE_NAME", ""),
            })
        return self.get_response(request)


class DeployErrorMiddleware:
    """Optional JSON error details while debugging production deploys."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            logger.exception("Unhandled request error on %s", request.path)
            # Only ever return tracebacks when DEBUG is also on: prevents an
            # accidentally-set env flag from leaking stack traces in prod.
            from django.conf import settings

            if settings.DEBUG and os.getenv("SHOW_DEPLOY_ERRORS", "").lower() in ("true", "1", "yes"):
                return JsonResponse(
                    {
                        "error": str(exc),
                        "type": type(exc).__name__,
                        "path": request.path,
                        "traceback": traceback.format_exc()[-3000:],
                    },
                    status=500,
                )
            raise


class TenantMiddleware:
    """Attach organization (tenant) to each authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Health endpoints must not require database connectivity.
        if request.path.startswith("/api/health") or request.path.rstrip("/") == "/ping":
            request.organization = None
            return self.get_response(request)
        request.organization = resolve_request_organization(request)
        return self.get_response(request)


class RequestIdMiddleware:
    """Attach a correlation id to each request/response for logs and audit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        expires_at = getattr(request, "session_expires_at", None)
        if expires_at:
            response["X-Session-Expires-At"] = expires_at
        return response


class SecurityHeadersMiddleware:
    """Add security headers not covered by Django's SecurityMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # API responses are JSON; a restrictive CSP is safe there and stops
        # any accidental HTML rendering from loading scripts. The Django
        # admin is excluded because it relies on its own inline assets.
        if request.path.startswith("/api/"):
            response.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; frame-ancestors 'none'",
            )
        return response
