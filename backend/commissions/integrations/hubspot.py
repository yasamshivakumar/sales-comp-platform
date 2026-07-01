"""HubSpot CRM connector: owners (users) and deals (orders)."""

import urllib.parse

from .base import BaseConnector, ConnectorError, http_get_json, http_post_json

HUBSPOT_API = "https://api.hubapi.com"


class HubSpotConnector(BaseConnector):
    provider = "hubspot"

    def _access_token(self):
        token = self.credentials.get("access_token") or self.credentials.get("api_key")
        if not token:
            raise ConnectorError("HubSpot private app access_token is required")
        return token

    def _headers(self):
        return {"Authorization": f"Bearer {self._access_token()}"}

    def _paginate_get(self, path, params=None, limit=None):
        params = dict(params or {})
        params.setdefault("limit", min(int(limit or 100), 100))
        records = []
        after = None
        while True:
            page_params = dict(params)
            if after:
                page_params["after"] = after
            url = f"{HUBSPOT_API}{path}?{urllib.parse.urlencode(page_params)}"
            payload = http_get_json(url, headers=self._headers())
            batch = payload.get("results") or []
            records.extend(batch)
            if limit and len(records) >= limit:
                return records[:limit]
            paging = payload.get("paging") or {}
            next_page = paging.get("next") or {}
            after = next_page.get("after")
            if not after:
                break
        return records

    def _paginate_search(self, object_type, filters, properties, limit=None):
        records = []
        after = None
        page_limit = min(int(limit or 100), 100) if limit else 100
        while True:
            body = {
                "filterGroups": [{"filters": filters}],
                "properties": properties,
                "limit": page_limit,
            }
            if after:
                body["after"] = after
            payload = http_post_json(
                f"{HUBSPOT_API}/crm/v3/objects/{object_type}/search",
                headers=self._headers(),
                body=body,
            )
            batch = payload.get("results") or []
            records.extend(batch)
            if limit and len(records) >= limit:
                return records[:limit]
            paging = payload.get("paging") or {}
            next_page = paging.get("next") or {}
            after = next_page.get("after")
            if not after:
                break
        return records

    def _fetch_owners(self, limit=None):
        owners = self._paginate_get("/crm/v3/owners", limit=limit)
        normalized = []
        for owner in owners:
            first = (owner.get("firstName") or "").strip()
            last = (owner.get("lastName") or "").strip()
            full_name = f"{first} {last}".strip() or owner.get("email") or str(owner.get("id", ""))
            normalized.append({
                "id": str(owner.get("id", "")),
                "email": owner.get("email") or "",
                "firstName": first,
                "lastName": last,
                "full_name": full_name,
            })
        return normalized

    def _fetch_deals(self, limit=None):
        section = self.config.get("orders") or {}
        deal_stages = section.get("deal_stages") or ["closedwon"]
        properties = section.get("properties") or [
            "amount",
            "closedate",
            "hubspot_owner_id",
            "dealname",
            "dealstage",
            "hs_currency",
        ]
        filters = [{
            "propertyName": "dealstage",
            "operator": "IN",
            "values": list(deal_stages),
        }]
        raw_deals = self._paginate_search("deals", filters, properties, limit=limit)
        normalized = []
        for deal in raw_deals:
            props = deal.get("properties") or {}
            normalized.append({
                "id": str(deal.get("id", "")),
                "amount": props.get("amount"),
                "closedate": props.get("closedate"),
                "hubspot_owner_id": props.get("hubspot_owner_id"),
                "dealname": props.get("dealname"),
                "dealstage": props.get("dealstage"),
                "currency": props.get("hs_currency") or props.get("deal_currency_code"),
            })
        return normalized

    def fetch_records(self, resource_type, limit=None):
        if resource_type == "users":
            return self._fetch_owners(limit=limit)
        if resource_type == "orders":
            return self._fetch_deals(limit=limit)
        raise ConnectorError(f"Unsupported resource type: {resource_type}")

    def test_connection(self):
        self._paginate_get("/crm/v3/owners", params={"limit": 1}, limit=1)
        return True
