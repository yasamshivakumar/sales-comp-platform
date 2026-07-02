"""Zoho CRM connector: users and deals (orders)."""

import logging
import urllib.parse

from django.utils.dateparse import parse_datetime

from .base import BaseConnector, ConnectorError, http_get_json

logger = logging.getLogger("commissions")


class ZohoConnector(BaseConnector):
    provider = "zoho"

    def _api_base(self):
        domain = (self.credentials.get("api_domain") or "https://www.zohoapis.com").rstrip(
            "/"
        )
        version = self.config.get("api_version") or "v2"
        return f"{domain}/crm/{version}"

    def _access_token(self):
        token = self.credentials.get("access_token")
        if not token:
            raise ConnectorError("Zoho OAuth access_token is required")
        return token

    def _headers(self):
        return {"Authorization": f"Zoho-oauthtoken {self._access_token()}"}

    def _paginate_records(self, module, *, limit=None, since=None, extra_params=None):
        params = dict(extra_params or {})
        if since:
            if hasattr(since, "isoformat"):
                params["modified_since"] = since.strftime("%Y-%m-%dT%H:%M:%S%z")
            else:
                params["modified_since"] = str(since)
        records = []
        page = 1
        per_page = min(int(limit or 200), 200)
        params.setdefault("per_page", per_page)
        while True:
            params["page"] = page
            url = f"{self._api_base()}/{module}?{urllib.parse.urlencode(params)}"
            payload = http_get_json(url, headers=self._headers())
            batch = payload.get("data") or []
            records.extend(batch)
            if limit and len(records) >= limit:
                return records[:limit]
            info = payload.get("info") or {}
            if not info.get("more_records"):
                break
            page += 1
        return records

    def _normalize_user(self, row):
        owner = row.get("owner") or {}
        owner_id = str(owner.get("id") or row.get("id") or "").strip()
        email = str(row.get("email") or owner.get("email") or "").strip().lower()
        if not email and owner_id:
            email = f"zoho-user-{owner_id}@crm.import"
        first = str(row.get("first_name") or "").strip()
        last = str(row.get("last_name") or "").strip()
        full_name = str(row.get("full_name") or f"{first} {last}".strip() or email).strip()
        return {
            "id": owner_id,
            "email": email,
            "full_name": full_name,
            "firstName": first,
            "lastName": last,
        }

    def _normalize_deal(self, row):
        owner = row.get("Owner") or row.get("owner") or {}
        owner_id = str(owner.get("id") or "").strip()
        close_date = row.get("Closing_Date") or row.get("closing_date")
        if close_date and isinstance(close_date, str) and "T" in close_date:
            parsed = parse_datetime(close_date)
            if parsed:
                close_date = parsed.date().isoformat()
        return {
            "id": str(row.get("id") or ""),
            "amount": row.get("Amount") or row.get("amount"),
            "closedate": close_date,
            "crm_owner_id": owner_id,
            "dealstage": row.get("Stage") or row.get("stage"),
            "currency": row.get("Currency") or row.get("currency"),
            "dealname": row.get("Deal_Name") or row.get("deal_name"),
        }

    def _fetch_users(self, limit=None, since=None):
        section = self.config.get("users") or {}
        module = section.get("module") or "users"
        raw = self._paginate_records(module, limit=limit, since=since)
        return [self._normalize_user(row) for row in raw]

    def _fetch_deals(self, limit=None, since=None):
        section = self.config.get("orders") or {}
        module = section.get("module") or "Deals"
        extra_params = dict(section.get("query_params") or {})
        stage = section.get("deal_stage")
        if stage:
            extra_params.setdefault("criteria", f"(Stage:equals:{stage})")
        raw = self._paginate_records(
            module,
            limit=limit,
            since=since,
            extra_params=extra_params,
        )
        return [self._normalize_deal(row) for row in raw]

    def fetch_records(self, resource_type, limit=None, since=None):
        if resource_type == "users":
            return self._fetch_users(limit=limit, since=since)
        if resource_type == "orders":
            return self._fetch_deals(limit=limit, since=since)
        raise ConnectorError(f"Unsupported resource type: {resource_type}")

    def test_connection(self):
        self._paginate_records("users", limit=1)
        return True
