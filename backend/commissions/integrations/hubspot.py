"""HubSpot CRM connector: owners (users) and deals (orders)."""

import logging
import urllib.parse

from .base import BaseConnector, ConnectorError, http_get_json, http_post_json

HUBSPOT_API = "https://api.hubapi.com"
logger = logging.getLogger("commissions")


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

    def _normalize_owner(self, owner):
        first = (owner.get("firstName") or "").strip()
        last = (owner.get("lastName") or "").strip()
        owner_id = str(owner.get("id", "")).strip()
        user_id = str(owner.get("userId") or owner.get("userIdIncludingInactive") or "").strip()
        email = (owner.get("email") or "").strip()
        if not email and owner_id:
            email = f"hubspot-owner-{owner_id}@crm.import"
        full_name = f"{first} {last}".strip() or email or owner_id
        return {
            "id": owner_id,
            "userId": user_id,
            "email": email,
            "firstName": first,
            "lastName": last,
            "full_name": full_name,
        }

    def fetch_owner(self, owner_id):
        """Fetch a single owner by HubSpot owner id (used on deals)."""
        owner_id = str(owner_id or "").strip()
        if not owner_id:
            return None
        for candidate in (owner_id, owner_id.split(".", 1)[0]):
            try:
                payload = http_get_json(
                    f"{HUBSPOT_API}/crm/v3/owners/{candidate}",
                    headers=self._headers(),
                )
                if payload:
                    return self._normalize_owner(payload)
            except ConnectorError as exc:
                logger.warning("HubSpot fetch_owner(%s) failed: %s", candidate, exc)
        return None

    def _fetch_owners(self, limit=None):
        active = self._paginate_get("/crm/v3/owners", limit=limit)
        archived = self._paginate_get(
            "/crm/v3/owners",
            params={"archived": "true"},
            limit=limit,
        )
        seen = set()
        owners = []
        for owner in active + archived:
            owner_key = str(owner.get("id", "")).strip()
            if not owner_key or owner_key in seen:
                continue
            seen.add(owner_key)
            owners.append(owner)
        return [self._normalize_owner(owner) for owner in owners]

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
