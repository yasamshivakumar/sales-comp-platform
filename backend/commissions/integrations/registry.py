from .base import BaseConnector
from .generic_rest import GenericRestConnector
from .salesforce import SalesforceConnector
from .webhook import WebhookConnector


PROVIDER_CHOICES = [
    {
        "id": "salesforce",
        "name": "Salesforce",
        "description": "Pull users and opportunities via SOQL (OAuth or access token).",
        "supports_pull_users": True,
        "supports_pull_orders": True,
        "supports_webhook": False,
    },
    {
        "id": "generic_rest",
        "name": "Generic REST API",
        "description": "Pull JSON from any CRM or middleware HTTP endpoint.",
        "supports_pull_users": True,
        "supports_pull_orders": True,
        "supports_webhook": False,
    },
    {
        "id": "webhook",
        "name": "Webhook / Zapier / Make",
        "description": "CRM pushes users or orders to Incentra via HTTP POST.",
        "supports_pull_users": False,
        "supports_pull_orders": False,
        "supports_webhook": True,
    },
    {
        "id": "hubspot",
        "name": "HubSpot (via REST)",
        "description": "Use Generic REST with HubSpot CRM API URLs, or Webhook from HubSpot workflows.",
        "supports_pull_users": True,
        "supports_pull_orders": True,
        "supports_webhook": True,
    },
]

DEFAULT_CONFIG = {
    "salesforce": {
        "api_version": "v58.0",
        "users": {
            "soql": (
                "SELECT Email, Name, Username, EmployeeNumber, Title "
                "FROM User WHERE IsActive = true"
            ),
            "field_map": {
                "email": "Email",
                "name": "Name",
                "username": "Username",
                "employee_id": "EmployeeNumber",
                "title": "Title",
                "role": "=Sales Rep",
            },
        },
        "orders": {
            "soql": (
                "SELECT Id, Name, Amount, CloseDate, OwnerId, StageName "
                "FROM Opportunity WHERE IsClosed = true AND IsWon = true"
            ),
            "field_map": {
                "order_id": "Id",
                "sales_amount": "Amount",
                "order_date": "CloseDate",
                "employee_id": "OwnerId",
                "order_status": "=Booked",
                "currency": "=INR",
            },
        },
    },
    "generic_rest": {
        "users": {
            "url": "",
            "json_path": "data",
            "field_map": {
                "email": "email",
                "name": "name",
                "employee_id": "employee_id",
                "role": "role",
            },
        },
        "orders": {
            "url": "",
            "json_path": "data",
            "field_map": {
                "order_id": "order_id",
                "order_date": "order_date",
                "employee_id": "employee_id",
                "sales_amount": "sales_amount",
            },
        },
    },
    "webhook": {
        "users": {"json_path": "records", "field_map": {}},
        "orders": {"json_path": "records", "field_map": {}},
    },
}


def get_connector(integration):
    mapping = {
        "salesforce": SalesforceConnector,
        "generic_rest": GenericRestConnector,
        "webhook": WebhookConnector,
        "hubspot": GenericRestConnector,
    }
    cls = mapping.get(integration.provider)
    if not cls:
        raise ValueError(f"Unknown provider: {integration.provider}")
    return cls(integration)


def list_providers():
    return PROVIDER_CHOICES
