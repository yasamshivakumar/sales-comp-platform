# Audit Log / Activity & Compliance Center Architecture

Incentra's compliance trail is the existing `AuditLog` model, upgraded into an
**Enterprise Activity & Compliance Center**. This document describes schema,
APIs, event capture, search, retention, and compliance controls.

## Goals

Every activity answers:

| Question | Fields |
|----------|--------|
| Who | `user`, `user_email`, `employee_id`, `role` |
| What | `action`, `module`, `entity_type`, `entity_id`, `changed_fields` |
| When | `created_at`, `duration_ms` |
| Where | `ip_address`, `user_agent`, `device`, `organization`, `business_unit` |
| Why | `reason` (optional) |
| From → To | `old_value`, `new_value` |
| Result | `status` (`success` / `failed` / `cancelled`) |
| Source | `source` (`web` / `api` / `csv_import` / `crm_sync` / `background_job`) |
| Correlation | `request_id` (correlation ID), `session_id` |

## Database schema

Table: `commissions_auditlog` (model `AuditLog`)

### Core (legacy, retained)

- `id` — primary key
- `organization_id` — tenant FK (CASCADE on org wipe)
- `user_id` — actor FK (SET_NULL)
- `user_email` — denormalized email
- `action` — stable action code (max 64)
- `plan_version_id` — optional plan version FK
- `detail` — free-form JSON (secrets redacted); kept for backward compatibility
- `ip_address`
- `request_id` — correlation / request ID
- `created_at`

### Enterprise extensions

- `employee_id`, `role`, `business_unit` — actor snapshot at write time
- `module` — logical product area (see catalog)
- `entity_type`, `entity_id` — subject of the change
- `severity` — `info` | `warning` | `critical` | `success`
- `source` — channel that produced the event
- `status` — outcome
- `reason` — optional comment / why
- `old_value`, `new_value` — JSON maps of before/after
- `changed_fields` — JSON list of field names that differed
- `duration_ms` — optional operation timing
- `user_agent`, `device`, `session_id`
- `search_text` — denormalized blob for `icontains` search

### Indexes

- `(organization, -created_at)`
- `(organization, module, -created_at)`
- `(organization, severity, -created_at)`
- `(organization, action)`
- `(organization, entity_type, entity_id)`
- plus field indexes on `user_email`, `action`, `request_id`, `created_at`, `session_id`

Migration: `0057_audit_activity_center.py`

## Immutability

- Instance `save()` after insert raises (`_state.adding` only).
- Instance `delete()` raises.
- QuerySet `.update()` raises.
- Django admin: no add / change / delete.
- There is no public write/update/delete API.
- Organization CASCADE delete may still remove rows during tenant wipe (ops only).

## Writer

`commissions.audit.record_audit(...)`

- Never raises to callers.
- Redacts secrets via `credential_crypto.redact_secrets`.
- Resolves module/severity/entity defaults from `audit_catalog.resolve_action`.
- Lifts legacy `detail.from` / `detail.to` into `old_value` / `new_value`.
- Snapshots profile employee id / role / business group.
- Captures IP, User-Agent → device, session (token/device/session key), correlation id.

Helpers: `diff_fields(old, new)`, `get_client_ip`, `get_request_id`.

## Action catalog

`commissions.audit_catalog.ACTION_CATALOG` maps action codes to:

- `module`, `severity`, `entity_type`, `label`, `icon`

Prefix rules cover dynamic actions (`integration_sync_*`, `commission_*`, etc.).

Tracked modules include: dashboard, orders, commissions, payouts, compensation
plans, rate tables, commission rules, quotas, bonuses, accelerators,
participants, people & access, CRM integrations, payroll, reports, organization
settings, authentication, roles & permissions, API keys, audit log.

## API endpoints

All require authentication. Tenant scoped to `request.organization`.

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/api/audit-logs/` | Admin/Finance or `view_audit` | Timeline / table (paginated + filters) |
| GET | `/api/audit-logs/<id>/` | same | Activity detail |
| GET | `/api/audit-logs/summary/` | same | Today's KPI cards |
| GET | `/api/audit-logs/security/` | same | Security / failed subset |
| GET | `/api/audit-logs/export/` | Admin or `export_audit` | CSV export (self-audited) |

### List filters

`date_from`, `date_to`, `module`, `user` / `user_email`, `role`, `severity`,
`status`, `source`, `action`, `entity_type`, `business_unit`, `plan_id`,
`q` / `search`, `page`, `page_size` (or legacy `limit`).

### Permissions

Role defaults (`people_ops.ROLE_PERMISSIONS`):

- Admin: `view_audit`, `export_audit`
- Finance: `view_audit`, `export_audit`
- Manager / Sales Rep: neither (nav removed for managers)

Custom permission matrices may grant these codes.

## Search architecture

1. On write, populate `search_text` from email, action, module, employee id,
   entity ids, IP, correlation id, session id, reason, changed fields.
2. List `q` filter uses `icontains` across `search_text` and key columns.
3. Composite org+time indexes keep timeline scans tenant-local.

No external search engine is required for the pilot/enterprise MVP scale.

## Retention policy

- Setting: `AUDIT_RETENTION_DAYS` (default **365**).
- Documented for compliance; **no automatic purge** in application code.
- Future SOC2 ops sprint may add archive/export-before-delete jobs.
- Exports are themselves logged as `audit_export`.

## UI

Route: `/audit-logs` — `frontend/src/Enterprise/AuditLogs.js`

- Summary cards, sticky filters, Timeline | Table toggle
- Detail drawer: Who / What / When / Where / Why / field diffs / JSON / related
- Export CSV

Nav label: **Activity & Compliance** (Admin + Finance menus).

## Compliance considerations

- Immutable append-only application semantics
- Secret redaction on write
- Tenant isolation on every read API
- Export restricted and audited
- Correlation IDs via `RequestIdMiddleware` (`X-Request-ID`)
- Field-level before/after for privileged people changes (role, quota)

## Embedded reuse

Plan activity, people workspace audit tabs, commission ops, and integration
center continue to query the same `AuditLog` table with scoped filters.
