from .base import BaseConnector, ConnectorError, http_get_json
from .mapper import extract_records
import urllib.parse


class GenericRestConnector(BaseConnector):
    provider = "generic_rest"

    def _auth_headers(self):
        headers = dict(self.credentials.get("headers") or {})
        auth_type = (self.credentials.get("auth_type") or "bearer").lower()
        token = self.credentials.get("api_key") or self.credentials.get("access_token")
        if token and auth_type == "bearer":
            headers.setdefault("Authorization", f"Bearer {token}")
        elif token and auth_type == "api_key_header":
            header_name = self.credentials.get("api_key_header") or "X-API-Key"
            headers.setdefault(header_name, token)
        return headers

    def fetch_records(self, resource_type, limit=None, since=None):
        section = self.config.get(resource_type) or {}
        url = section.get("url") or self.config.get(f"{resource_type}_url")
        if not url:
            raise ConnectorError(f"No URL configured for {resource_type}")
        if since and "{since_iso}" in url:
            since_iso = since.isoformat() if hasattr(since, "isoformat") else str(since)
            url = url.replace("{since_iso}", urllib.parse.quote(since_iso))
        payload = http_get_json(url, headers=self._auth_headers())
        records = extract_records(payload, section.get("json_path") or "")
        if limit:
            return records[: int(limit)]
        return records

    def test_connection(self):
        self.fetch_records("users", limit=1)
        return True
