"""Shared security helpers: CSV hardening, upload limits, login lockout."""

import csv
import io
import ipaddress
import logging
import socket

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("commissions")


# ---------------------------------------------------------------------------
# CSV export: formula-injection sanitization
# ---------------------------------------------------------------------------

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value):
    """Neutralize spreadsheet formula injection.

    A cell beginning with = + - @ (or tab/CR) is treated as a formula by
    Excel/Sheets, so text like `=HYPERLINK(...)` in an employee name would
    execute when a finance user opens the export. Prefixing with a single
    quote makes the cell inert without changing how numbers/dates that we
    emit as native types are rendered.
    """
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return value
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def sanitize_csv_row(row):
    return [sanitize_csv_cell(cell) for cell in row]


# ---------------------------------------------------------------------------
# CSV upload limits
# ---------------------------------------------------------------------------

class CsvValidationError(Exception):
    """Raised with a safe, user-facing message."""


def max_upload_bytes():
    return int(getattr(settings, "MAX_IMPORT_FILE_BYTES", 10 * 1024 * 1024))


def max_upload_rows():
    return int(getattr(settings, "MAX_IMPORT_ROWS", 50000))


def read_csv_upload(uploaded_file):
    """Validate and parse an uploaded CSV; returns (decoded_text, rows).

    Enforces file size and row-count caps before/while materializing rows so
    an oversized upload cannot exhaust worker memory.
    """
    limit = max_upload_bytes()
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > limit:
        raise CsvValidationError(
            f"File is too large ({size // (1024 * 1024)} MB). "
            f"Maximum allowed is {limit // (1024 * 1024)} MB."
        )

    raw = uploaded_file.read(limit + 1)
    if len(raw) > limit:
        raise CsvValidationError(
            f"File is too large. Maximum allowed is {limit // (1024 * 1024)} MB."
        )
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError(
            "File is not valid UTF-8 text. Save it as CSV (UTF-8) and retry."
        ) from exc

    row_cap = max_upload_rows()
    rows = []
    try:
        reader = csv.DictReader(io.StringIO(decoded))
        for row in reader:
            rows.append(row)
            if len(rows) > row_cap:
                raise CsvValidationError(
                    f"Too many rows. Maximum allowed is {row_cap}."
                )
    except csv.Error as exc:
        logger.warning("CSV parse error on upload: %s", exc)
        raise CsvValidationError("File could not be parsed as CSV.") from exc

    return decoded, rows


# ---------------------------------------------------------------------------
# Login protection: lockout + IP extraction
# ---------------------------------------------------------------------------

def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def _lockout_settings():
    return (
        int(getattr(settings, "LOGIN_LOCKOUT_THRESHOLD", 8)),
        int(getattr(settings, "LOGIN_LOCKOUT_WINDOW_SECONDS", 900)),
        int(getattr(settings, "LOGIN_LOCKOUT_DURATION_SECONDS", 900)),
    )


def _failure_keys(email, ip):
    email = (email or "").strip().lower()
    return (
        f"login-failures:email:{email}",
        f"login-failures:ip:{ip}",
    )


def login_locked_out(email, ip):
    threshold, _, _ = _lockout_settings()
    for key in _failure_keys(email, ip):
        if (cache.get(key) or 0) >= threshold:
            return True
    return False


def record_login_failure(email, ip):
    threshold, window, lock_duration = _lockout_settings()
    for key in _failure_keys(email, ip):
        current = cache.get(key) or 0
        # Extend TTL to the lock duration once the threshold is crossed.
        ttl = lock_duration if current + 1 >= threshold else window
        cache.set(key, current + 1, ttl)


def clear_login_failures(email, ip):
    cache.delete_many(list(_failure_keys(email, ip)))


# ---------------------------------------------------------------------------
# SSRF guard for outbound integration requests
# ---------------------------------------------------------------------------

def is_public_host(hostname):
    """True when the hostname resolves only to public (global) addresses.

    Blocks loopback, RFC1918, link-local (incl. 169.254.169.254 cloud
    metadata), and reserved ranges so tenant-supplied integration URLs
    cannot be used to scan or read internal services.
    """
    if getattr(settings, "INTEGRATIONS_ALLOW_PRIVATE_URLS", False):
        return True
    hostname = str(hostname or "").strip("[]")
    if not hostname:
        return False
    try:
        addresses = {
            info[4][0] for info in socket.getaddrinfo(hostname, None)
        }
    except (socket.gaierror, UnicodeError):
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True
