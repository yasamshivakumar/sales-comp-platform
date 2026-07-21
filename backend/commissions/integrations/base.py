import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("commissions")


class ConnectorError(Exception):
    pass


def assert_http_url(url):
    """Reject non-HTTP(S) schemes and non-public hosts before urlopen.

    Integration URLs are tenant-admin supplied, so without the host check a
    tenant could point a connector at localhost, RFC1918 ranges, or the cloud
    metadata endpoint (169.254.169.254) to read internal services (SSRF).
    """
    from ..security import is_public_host

    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConnectorError("Only http(s) URLs are allowed for CRM requests")
    if not is_public_host(parsed.hostname):
        raise ConnectorError(
            "CRM URL host is not allowed (private, loopback, or unresolvable)"
        )
    return url


class BaseConnector:
    provider = "base"

    def __init__(self, integration):
        self.integration = integration
        self.credentials = integration.credentials or {}
        self.config = integration.config or {}

    def test_connection(self):
        self.fetch_records("users", limit=1)
        return True

    def fetch_records(self, resource_type, limit=None, since=None):
        raise NotImplementedError


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect target so a public URL cannot bounce
    the request to an internal/private address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        assert_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirectHandler())


def _http_request(method, url, headers=None, body=None, timeout=60):
    assert_http_url(url)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method=method.upper(),
    )
    try:
        with _opener.open(request, timeout=timeout) as response:  # nosec B310
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ConnectorError(
                    f"Invalid JSON response from {url}: {raw[:200]}"
                ) from exc
            if not isinstance(data, dict):
                raise ConnectorError(
                    f"Unexpected response type from {url}: expected object, got {type(data).__name__}"
                )
            return data
    except ConnectorError:
        raise
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        # Avoid logging full bodies (may include tokens or PII).
        safe_detail = detail[:200].replace("\n", " ")
        logger.warning("HTTP %s from CRM endpoint", exc.code)
        raise ConnectorError(f"HTTP {exc.code}: {safe_detail}") from exc
    except urllib.error.URLError as exc:
        logger.warning("CRM request failed: %s", exc.reason)
        raise ConnectorError("CRM request failed") from exc


def http_get_json(url, headers=None, timeout=60):
    return _http_request("GET", url, headers=headers, timeout=timeout)


def http_post_json(url, headers=None, body=None, timeout=60):
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    return _http_request("POST", url, headers=headers, body=body, timeout=timeout)
