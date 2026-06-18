from .base import BaseConnector, ConnectorError
from .mapper import extract_records


class WebhookConnector(BaseConnector):
    """Pull is not supported — data is pushed to the webhook endpoint."""

    provider = "webhook"

    def fetch_records(self, resource_type, limit=None):
        raise ConnectorError(
            "Webhook integrations receive data via POST to the webhook URL; "
            "use Sync after pushing data or configure a REST/Salesforce connector to pull."
        )

    def test_connection(self):
        return True

    @staticmethod
    def normalize_inbound_payload(payload, resource_type, config):
        if isinstance(payload, list):
            return payload
        path = (config.get(resource_type) or {}).get("json_path") or "records"
        return extract_records(payload, path)
