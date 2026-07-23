import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from .base import BaseConnector, ConnectorError, assert_http_url, http_get_json

logger = logging.getLogger("commissions")


class SalesforceConnector(BaseConnector):
    provider = "salesforce"

    def _api_version(self):
        return self.config.get("api_version") or "v58.0"

    def _instance_url(self):
        url = (self.credentials.get("instance_url") or "").rstrip("/")
        if not url:
            raise ConnectorError("Salesforce instance_url is required")
        return url

    def _access_token(self):
        token = self.credentials.get("access_token")
        if token:
            return token
        return self._login_password_flow()

    def _login_password_flow(self):
        client_id = self.credentials.get("client_id")
        client_secret = self.credentials.get("client_secret")
        username = self.credentials.get("username")
        password = self.credentials.get("password")
        security_token = self.credentials.get("security_token") or ""
        login_url = (
            self.credentials.get("login_url")
            or "https://login.salesforce.com/services/oauth2/token"
        )
        if not all([client_id, client_secret, username, password]):
            raise ConnectorError(
                "Provide access_token or OAuth client_id, client_secret, username, password"
            )
        assert_http_url(login_url)
        payload = urllib.parse.urlencode({
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": f"{password}{security_token}",
        }).encode("utf-8")

        request = urllib.request.Request(
            login_url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            logger.warning("Salesforce login HTTP error: %s", exc.code)
            raise ConnectorError("Salesforce login failed") from exc
        except urllib.error.URLError as exc:
            logger.warning("Salesforce login request failed: %s", exc.reason)
            raise ConnectorError("Salesforce login failed") from exc

        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ConnectorError("Salesforce login returned invalid JSON") from exc

        if not isinstance(parsed, dict):
            raise ConnectorError("Salesforce login returned an unexpected response")

        token = parsed.get("access_token")
        if not token:
            error_code = parsed.get("error") or "unknown_error"
            error_desc = parsed.get("error_description") or "no access_token"
            logger.warning(
                "Salesforce login failed: %s (%s)",
                error_code,
                error_desc,
            )
            raise ConnectorError(f"Salesforce login failed: {error_code}")

        self.credentials["access_token"] = token
        instance_url = parsed.get("instance_url")
        if instance_url:
            self.credentials["instance_url"] = instance_url
        if hasattr(self.integration, "set_encrypted_credentials"):
            self.integration.set_encrypted_credentials(self.credentials)
            self.integration.save(
                update_fields=["credentials", "encrypted_credentials", "updated_at"]
            )
        return token

    def _query(self, soql, limit=None):
        token = self._access_token()
        base = self._instance_url()
        version = self._api_version()
        query = soql.strip()
        if limit and " limit " not in query.lower():
            query = f"{query} LIMIT {int(limit)}"
        url = (
            f"{base}/services/data/{version}/query?"
            f"{urllib.parse.urlencode({'q': query})}"
        )
        headers = {"Authorization": f"Bearer {token}"}
        records = []
        while url:
            payload = http_get_json(url, headers=headers)
            if not isinstance(payload, dict):
                raise ConnectorError("Salesforce query returned an unexpected response")
            records.extend(payload.get("records") or [])
            next_url = payload.get("nextRecordsUrl")
            if not next_url:
                break
            url = f"{base}{next_url}" if next_url.startswith("/") else next_url
            if limit and len(records) >= limit:
                records = records[:limit]
                break
        cleaned = []
        for row in records:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item.pop("attributes", None)
            cleaned.append(item)
        return cleaned

    def fetch_records(self, resource_type, limit=None, since=None):
        section = self.config.get(resource_type) or {}
        soql = section.get("soql")
        if not soql:
            raise ConnectorError(f"No SOQL configured for {resource_type}")
        if since and resource_type == "orders":
            soql = self._apply_incremental_soql(soql, since)
        return self._query(soql, limit=limit)

    def _apply_incremental_soql(self, soql, since):
        """Append LastModifiedDate filter for incremental order sync."""
        if "lastmodifieddate" in soql.lower():
            return soql
        if hasattr(since, "strftime"):
            since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            since_iso = str(since)
        clause = f"LastModifiedDate >= {since_iso}"
        upper = soql.upper()
        if " WHERE " in upper:
            return f"{soql} AND {clause}"
        if " FROM " in upper:
            parts = soql.rsplit("FROM", 1)
            return f"{parts[0]}FROM{parts[1]} WHERE {clause}"
        return soql

    def test_connection(self):
        self._query("SELECT Id FROM User LIMIT 1")
        return True
