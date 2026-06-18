"""Map external CRM records to Incentra user/order row dicts."""

from datetime import datetime


def _get_nested(record, path):
    if not path:
        return record
    value = record
    for part in str(path).split("."):
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def map_record(record, field_map, defaults=None):
    """Apply field_map {internal_key: external_path_or_literal}."""
    defaults = defaults or {}
    mapped = dict(defaults)
    for internal_key, external_key in (field_map or {}).items():
        if external_key is None:
            continue
        if isinstance(external_key, str) and external_key.startswith("="):
            mapped[internal_key] = external_key[1:]
            continue
        value = _get_nested(record, external_key)
        if value is not None and value != "":
            mapped[internal_key] = value
    return mapped


def map_records(records, field_map, defaults=None):
    return [map_record(row, field_map, defaults) for row in records]


def extract_records(payload, json_path):
    """Extract list from API response using dot path (empty = payload if list)."""
    if json_path:
        value = _get_nested(payload, json_path)
    elif isinstance(payload, list):
        value = payload
    else:
        value = payload
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def normalize_date_value(value):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    text = str(value).strip()
    if "T" in text:
        text = text.split("T")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text
