import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("commissions")


class ConnectorError(Exception):
    pass


class BaseConnector:
    provider = "base"

    def __init__(self, integration):
        self.integration = integration
        self.credentials = integration.credentials or {}
        self.config = integration.config or {}

    def test_connection(self):
        self.fetch_records("users", limit=1)
        return True

    def fetch_records(self, resource_type, limit=None):
        raise NotImplementedError


def _http_request(method, url, headers=None, body=None, timeout=60):
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ConnectorError(f"HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise ConnectorError(str(exc)) from exc


def http_get_json(url, headers=None, timeout=60):
    return _http_request("GET", url, headers=headers, timeout=timeout)


def http_post_json(url, headers=None, body=None, timeout=60):
    headers = dict(headers or {})
    headers.setdefault("Content-Type", "application/json")
    return _http_request("POST", url, headers=headers, body=body, timeout=timeout)
