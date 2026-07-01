import uuid

from .tenants import resolve_request_organization


class TenantMiddleware:
    """Attach organization (tenant) to each authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Liveness checks must not require database connectivity.
        if request.path.startswith("/api/health") and not request.path.startswith(
            "/api/health/ready"
        ):
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
        return response
