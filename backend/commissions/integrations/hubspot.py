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

    def _normalize_owner(self, owner, *, include_inactive_user_id=False):
        first = (owner.get("firstName") or "").strip()
        last = (owner.get("lastName") or "").strip()
        owner_id = str(owner.get("id", "")).strip()
        user_id = str(owner.get("userId") or "").strip()
        if not user_id and include_inactive_user_id:
            user_id = str(owner.get("userIdIncludingInactive") or "").strip()
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
            "archived": bool(owner.get("archived")),
        }

    def _is_active_owner(self, owner):
        if owner.get("archived") is True:
            return False
        # Deactivated HubSpot users keep an owner id but lose userId.
        if owner.get("userId") is None and owner.get("userIdIncludingInactive"):
            return False
        return True

    def _fetch_archived_owner_by_id(self, owner_id):
        archived = self._paginate_get(
            "/crm/v3/owners",
            params={"archived": "true"},
        )
        for owner in archived:
            if str(owner.get("id", "")).strip() == owner_id:
                return self._normalize_owner(owner, include_inactive_user_id=True)
        return None

    def fetch_owner(self, owner_id, *, for_resolution=False):
        """
        Fetch a single owner by HubSpot owner id.

        User sync uses active owners only. Deal resolution may look up archived
        owners so historical deals still map to existing Incentra employees.
        """
        owner_id = str(owner_id or "").strip()
        if not owner_id:
            return None
        candidates = {owner_id, owner_id.split(".", 1)[0]}
        for candidate in candidates:
            for url in (
                f"{HUBSPOT_API}/crm/v3/owners/{candidate}",
                f"{HUBSPOT_API}/crm/v3/owners/{candidate}?archived=true",
            ):
                try:
                    payload = http_get_json(url, headers=self._headers())
                    if not payload:
                        continue
                    normalized = self._normalize_owner(
                        payload,
                        include_inactive_user_id=for_resolution,
                    )
                    if normalized.get("archived") and not for_resolution:
                        continue
                    return normalized
                except ConnectorError as exc:
                    logger.warning("HubSpot fetch_owner(%s) failed: %s", url, exc)
        if for_resolution:
            return self._fetch_archived_owner_by_id(owner_id)
        return None

    def _fetch_owners(self, limit=None):
        """Pull active HubSpot owners only (excludes archived/deactivated users)."""
        raw = self._paginate_get("/crm/v3/owners", limit=limit)
        owners = []
        for owner in raw:
            if not self._is_active_owner(owner):
                continue
            owners.append(self._normalize_owner(owner))
        return owners

    def _normalize_deal_record(self, deal):
        props = deal.get("properties") or {}
        return {
            "id": str(deal.get("id", "")),
            "amount": props.get("amount"),
            "closedate": props.get("closedate"),
            "hubspot_owner_id": props.get("hubspot_owner_id"),
            "dealname": props.get("dealname"),
            "dealstage": props.get("dealstage"),
            "currency": props.get("hs_currency") or props.get("deal_currency_code"),
        }

    def _fetch_deals(self, limit=None, since=None):
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
        if since:
            if hasattr(since, "timestamp"):
                since_ms = str(int(since.timestamp() * 1000))
            else:
                since_ms = str(since)
            filters.append({
                "propertyName": "hs_lastmodifieddate",
                "operator": "GTE",
                "value": since_ms,
            })
        raw_deals = self._paginate_search("deals", filters, properties, limit=limit)
        return [self._normalize_deal_record(deal) for deal in raw_deals]

    def fetch_deal_by_id(self, deal_id):
        section = self.config.get("orders") or {}
        properties = section.get("properties") or [
            "amount",
            "closedate",
            "hubspot_owner_id",
            "dealname",
            "dealstage",
            "hs_currency",
        ]
        deal_id = str(deal_id or "").strip()
        if not deal_id:
            return None
        params = urllib.parse.urlencode(
            {"properties": ",".join(properties)},
            quote_via=urllib.parse.quote,
        )
        payload = http_get_json(
            f"{HUBSPOT_API}/crm/v3/objects/deals/{deal_id}?{params}",
            headers=self._headers(),
        )
        if not payload:
            return None
        return self._normalize_deal_record(payload)

    def fetch_records(self, resource_type, limit=None, since=None):
        if resource_type == "users":
            return self._fetch_owners(limit=limit)
        if resource_type == "orders":
            return self._fetch_deals(limit=limit, since=since)
        raise ConnectorError(f"Unsupported resource type: {resource_type}")

    def test_connection(self):
        self._paginate_get("/crm/v3/owners", params={"limit": 1}, limit=1)
        return True
