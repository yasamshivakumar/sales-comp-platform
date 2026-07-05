import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("commissions")


class ConnectorError(Exception):
    pass


def assert_http_url(url):
    """Reject non-HTTP(S) schemes (file:, data:, etc.) before urlopen."""
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ConnectorError("Only http(s) URLs are allowed for CRM requests")
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
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
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
