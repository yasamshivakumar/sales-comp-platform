from .generic_rest import GenericRestConnector
from .hubspot import HubSpotConnector
from .salesforce import SalesforceConnector
from .webhook import WebhookConnector
from .zoho import ZohoConnector


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
        "name": "HubSpot",
        "description": "Pull owners and closed-won deals via HubSpot CRM API (private app token).",
        "supports_pull_users": True,
        "supports_pull_orders": True,
        "supports_webhook": True,
        "supports_auto_sync": True,
        "supports_full_sync": True,
    },
    {
        "id": "zoho",
        "name": "Zoho CRM",
        "description": "Pull users and closed deals via Zoho CRM API (OAuth access token).",
        "supports_pull_users": True,
        "supports_pull_orders": True,
        "supports_webhook": False,
        "supports_auto_sync": True,
        "supports_full_sync": True,
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
                "crm_user_id": "Id",
                "employee_id": "EmployeeNumber",
                "title": "Title",
                "role": "=Sales Rep",
            },
        },
        "orders": {
            "incremental_sync": True,
            "soql": (
                "SELECT Id, Name, Amount, CloseDate, OwnerId, StageName, CurrencyIsoCode "
                "FROM Opportunity WHERE IsClosed = true AND IsWon = true"
            ),
            "field_map": {
                "order_id": "Id",
                "sales_amount": "Amount",
                "order_date": "CloseDate",
                "crm_owner_id": "OwnerId",
                "order_status": "=Booked",
                "currency": "CurrencyIsoCode",
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
                "currency": "currency",
            },
        },
    },
    "webhook": {
        "users": {"json_path": "records", "field_map": {}},
        "orders": {"json_path": "records", "field_map": {}},
    },
    "hubspot": {
        "users": {
            "field_map": {
                "email": "email",
                "name": "full_name",
                "first_name": "firstName",
                "last_name": "lastName",
                "crm_user_id": "id",
                "crm_alt_user_id": "userId",
                "role": "=Sales Rep",
            },
        },
        "orders": {
            "incremental_sync": True,
            "deal_stages": ["closedwon"],
            "skip_archived_owners": True,
            "auto_import_owners": True,
            "auto_mark_success": True,
            "archived_owner_remap": {},
            "field_map": {
                "order_id": "id",
                "sales_amount": "amount",
                "order_date": "closedate",
                "crm_owner_id": "hubspot_owner_id",
                "order_status": "=Success",
                "currency": "currency",
            },
        },
    },
    "zoho": {
        "api_version": "v2",
        "users": {
            "module": "users",
            "field_map": {
                "email": "email",
                "name": "full_name",
                "first_name": "firstName",
                "last_name": "lastName",
                "crm_user_id": "id",
                "role": "=Sales Rep",
            },
        },
        "orders": {
            "incremental_sync": True,
            "module": "Deals",
            "deal_stage": "Closed Won",
            "auto_mark_success": True,
            "field_map": {
                "order_id": "id",
                "sales_amount": "amount",
                "order_date": "closedate",
                "crm_owner_id": "crm_owner_id",
                "order_status": "=Success",
                "currency": "currency",
            },
        },
    },
}


def get_connector(integration):
    mapping = {
        "salesforce": SalesforceConnector,
        "generic_rest": GenericRestConnector,
        "webhook": WebhookConnector,
        "hubspot": HubSpotConnector,
        "zoho": ZohoConnector,
    }
    cls = mapping.get(integration.provider)
    if not cls:
        raise ValueError(f"Unknown provider: {integration.provider}")
    return cls(integration)


def list_providers():
    return PROVIDER_CHOICES
