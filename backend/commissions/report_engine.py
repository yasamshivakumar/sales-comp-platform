"""
Dynamic reporting engine — metadata-driven queries over Incentra models.

Does not hardcode saved reports; definitions come from Report / fields / filters.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

from .models import (
    AuditLog,
    Commission,
    CompensationPlan,
    Order,
    PayoutRun,
    Report,
    UserProfile,
)
from .tenants import filter_queryset_by_organization


def _field(key, label, type_="string", path=None, filterable=True, sortable=True, groupable=False):
    return {
        "key": key,
        "label": label,
        "type": type_,
        "path": path or key,
        "filterable": filterable,
        "sortable": sortable,
        "groupable": groupable,
    }


DATASOURCES = {
    Report.DATASOURCE_COMMISSIONS: {
        "key": Report.DATASOURCE_COMMISSIONS,
        "label": "Commission Records",
        "roles": ("Admin", "Finance", "Manager"),
        "fields": [
            _field("employee_name", "Employee Name", path="employee__name", groupable=True),
            _field("employee_email", "Employee Email", path="employee__email"),
            _field("employee_id", "Employee ID", path="sale__order__employee_id", groupable=True),
            _field("amount", "Commission Amount", "number", "commission_amount", sortable=True),
            _field("status", "Status", path="status", groupable=True),
            _field("plan_name", "Plan", path="compensation_plan__plan_name", groupable=True),
            _field("period_start", "Period Start", "date", "period_start"),
            _field("period_end", "Period End", "date", "period_end"),
            _field("currency", "Currency", path="currency", groupable=True),
            _field("calculated_at", "Calculated At", "datetime", "calculated_at"),
            _field("order_date", "Order Date", "date", "sale__order__order_date"),
            _field("territory", "Territory", path="sale__order__territory__name", groupable=True),
            _field("region", "Region", path="sale__order__region", groupable=True),
        ],
        "default_fields": ["employee_name", "amount", "status", "plan_name", "period_start"],
        "default_sort": "amount",
    },
    Report.DATASOURCE_ORDERS: {
        "key": Report.DATASOURCE_ORDERS,
        "label": "Orders",
        "roles": ("Admin", "Finance", "Manager"),
        "fields": [
            _field("order_id", "Order ID", path="order_id"),
            _field("order_date", "Order Date", "date", "order_date", groupable=True),
            _field("employee_id", "Employee ID", path="employee_id", groupable=True),
            _field("sales_amount", "Revenue", "number", "sales_amount"),
            _field("product_name", "Product", path="product_name", groupable=True),
            _field("customer_name", "Customer", path="customer_name"),
            _field("region", "Region", path="region", groupable=True),
            _field("territory", "Territory", path="territory__name", groupable=True),
            _field("order_status", "Status", path="order_status", groupable=True),
            _field("currency", "Currency", path="currency"),
            _field("business_group", "Business Unit", path="business_group", groupable=True),
        ],
        "default_fields": ["order_id", "order_date", "employee_id", "sales_amount", "order_status"],
        "default_sort": "sales_amount",
    },
    Report.DATASOURCE_EMPLOYEES: {
        "key": Report.DATASOURCE_EMPLOYEES,
        "label": "Employees",
        "roles": ("Admin", "Finance", "Manager"),
        "fields": [
            _field("name", "Name", path="name", groupable=True),
            _field("employee_id", "Employee ID", path="employee_id"),
            _field("email", "Email", path="email"),
            _field("role", "Role", path="role", groupable=True),
            _field("department", "Department", path="department", groupable=True),
            _field("region", "Region / Market", path="market", groupable=True),
            _field("territory", "Territory", path="territory__name", groupable=True),
            _field("business_group", "Business Unit", path="business_group", groupable=True),
            _field("personal_target", "Quota", "number", "personal_target"),
            _field("plan_name", "Plan", path="assigned_compensation_plan__plan_name", groupable=True),
            _field("position_name", "Position", path="position_name", groupable=True),
        ],
        "default_fields": ["name", "employee_id", "role", "territory", "personal_target"],
        "default_sort": "name",
    },
    Report.DATASOURCE_PLANS: {
        "key": Report.DATASOURCE_PLANS,
        "label": "Compensation Plans",
        "roles": ("Admin", "Finance"),
        "fields": [
            _field("plan_name", "Plan Name", path="plan_name", groupable=True),
            _field("status", "Status", path="status", groupable=True),
            _field("role", "Role", path="role", groupable=True),
            _field("position_name", "Position", path="position_name"),
            _field("business_group", "Business Unit", path="business_group", groupable=True),
            _field("effective_start_date", "Start", "date", "effective_start_date"),
            _field("effective_end_date", "End", "date", "effective_end_date"),
            _field("commission_table_type", "Rate Table Type", path="commission_table_type"),
        ],
        "default_fields": ["plan_name", "status", "role", "effective_start_date"],
        "default_sort": "plan_name",
    },
    Report.DATASOURCE_PAYOUTS: {
        "key": Report.DATASOURCE_PAYOUTS,
        "label": "Payouts",
        "roles": ("Admin", "Finance"),
        "fields": [
            _field("name", "Payout Name", path="name"),
            _field("status", "Status", path="status", groupable=True),
            _field("start_date", "Start", "date", "start_date"),
            _field("end_date", "End", "date", "end_date"),
            _field("payment_reference", "Payment Reference", path="payment_reference"),
            _field("paid_at", "Paid At", "datetime", "paid_at"),
            _field("created_at", "Created At", "datetime", "created_at"),
        ],
        "default_fields": ["name", "status", "start_date", "end_date", "paid_at"],
        "default_sort": "created_at",
    },
    Report.DATASOURCE_QUOTAS: {
        "key": Report.DATASOURCE_QUOTAS,
        "label": "Quotas",
        "roles": ("Admin", "Finance", "Manager"),
        "fields": [
            _field("name", "Employee", path="name", groupable=True),
            _field("employee_id", "Employee ID", path="employee_id"),
            _field("role", "Role", path="role", groupable=True),
            _field("personal_target", "Quota", "number", "personal_target"),
            _field("territory", "Territory", path="territory__name", groupable=True),
            _field("department", "Department", path="department", groupable=True),
            _field("business_group", "Business Unit", path="business_group", groupable=True),
            _field("plan_name", "Plan", path="assigned_compensation_plan__plan_name", groupable=True),
        ],
        "default_fields": ["name", "employee_id", "personal_target", "territory", "plan_name"],
        "default_sort": "personal_target",
    },
    Report.DATASOURCE_AUDIT: {
        "key": Report.DATASOURCE_AUDIT,
        "label": "Audit Logs",
        "roles": ("Admin", "Finance"),
        "fields": [
            _field("created_at", "When", "datetime", "created_at"),
            _field("user_email", "User", path="user_email", groupable=True),
            _field("action", "Action", path="action", groupable=True),
            _field("module", "Module", path="module", groupable=True),
            _field("severity", "Severity", path="severity", groupable=True),
            _field("status", "Status", path="status", groupable=True),
            _field("source", "Source", path="source", groupable=True),
            _field("ip_address", "IP", path="ip_address"),
            _field("employee_id", "Employee ID", path="employee_id"),
        ],
        "default_fields": ["created_at", "user_email", "action", "module", "severity"],
        "default_sort": "created_at",
    },
}


def list_datasources_for_role(role_name):
    role = str(role_name or "").strip()
    out = []
    for meta in DATASOURCES.values():
        allowed = meta.get("roles") or ()
        if role in ("Admin", "Administrator") or role in allowed:
            out.append(
                {
                    "key": meta["key"],
                    "label": meta["label"],
                    "fields": meta["fields"],
                    "default_fields": meta["default_fields"],
                    "default_sort": meta.get("default_sort") or "",
                }
            )
    return out


def get_datasource(key):
    return DATASOURCES.get(key)


def _field_map(meta):
    return {f["key"]: f for f in meta["fields"]}


def _base_queryset(datasource, organization, request=None, profile=None, view_mode="organization"):
    if datasource == Report.DATASOURCE_COMMISSIONS:
        qs = Commission.objects.select_related(
            "employee", "compensation_plan", "sale__order", "sale__order__territory"
        )
        qs = filter_queryset_by_organization(qs, organization)
    elif datasource == Report.DATASOURCE_ORDERS:
        qs = Order.objects.select_related("territory")
        qs = filter_queryset_by_organization(qs, organization)
    elif datasource in (Report.DATASOURCE_EMPLOYEES, Report.DATASOURCE_QUOTAS):
        qs = UserProfile.objects.select_related("territory", "assigned_compensation_plan")
        qs = filter_queryset_by_organization(qs, organization)
    elif datasource == Report.DATASOURCE_PLANS:
        qs = CompensationPlan.objects.select_related("territory")
        qs = filter_queryset_by_organization(qs, organization)
    elif datasource == Report.DATASOURCE_PAYOUTS:
        qs = PayoutRun.objects.all()
        qs = filter_queryset_by_organization(qs, organization)
    elif datasource == Report.DATASOURCE_AUDIT:
        qs = AuditLog.objects.all()
        qs = filter_queryset_by_organization(qs, organization)
    else:
        raise ValueError(f"Unknown datasource: {datasource}")

    # Manager team scope for people/orders/commissions
    if view_mode == "team" and profile is not None:
        from .dashboard_ops import _manager_team_employee_ids

        eids = _manager_team_employee_ids(profile, organization)
        if datasource == Report.DATASOURCE_COMMISSIONS:
            emails = list(
                UserProfile.objects.filter(employee_id__in=eids).values_list("email", flat=True)
            )
            from django.db.models import Q

            qs = qs.filter(
                Q(sale__order__employee_id__in=eids) | Q(employee__email__in=emails)
            )
        elif datasource == Report.DATASOURCE_ORDERS:
            qs = qs.filter(employee_id__in=eids) if eids else qs.none()
        elif datasource in (Report.DATASOURCE_EMPLOYEES, Report.DATASOURCE_QUOTAS):
            qs = qs.filter(employee_id__in=eids) if eids else qs.none()
    elif view_mode == "self" and profile is not None:
        from django.db.models import Q

        if datasource == Report.DATASOURCE_COMMISSIONS:
            qs = qs.filter(
                Q(employee__email__iexact=profile.email)
                | Q(sale__order__employee_id=profile.employee_id)
            )
        elif datasource == Report.DATASOURCE_ORDERS:
            qs = qs.filter(employee_id=profile.employee_id)
        elif datasource in (Report.DATASOURCE_EMPLOYEES, Report.DATASOURCE_QUOTAS):
            qs = qs.filter(pk=profile.pk)
        elif datasource == Report.DATASOURCE_AUDIT:
            qs = qs.filter(user_email__iexact=profile.email or "")
        else:
            qs = qs.none()
    return qs


def _apply_filter(qs, path, operator, value, field_type):
    from django.db.models import Q

    if value in (None, "", {}, []):
        return qs
    if operator == "eq":
        return qs.filter(**{path: value})
    if operator == "ne":
        return qs.exclude(**{path: value})
    if operator == "contains":
        return qs.filter(**{f"{path}__icontains": value})
    if operator == "gte":
        return qs.filter(**{f"{path}__gte": value})
    if operator == "lte":
        return qs.filter(**{f"{path}__lte": value})
    if operator == "in":
        vals = value if isinstance(value, list) else str(value).split(",")
        return qs.filter(**{f"{path}__in": vals})
    if operator == "between":
        if isinstance(value, dict):
            start, end = value.get("from") or value.get("start"), value.get("to") or value.get("end")
        elif isinstance(value, (list, tuple)) and len(value) >= 2:
            start, end = value[0], value[1]
        else:
            return qs
        q = Q()
        if start:
            q &= Q(**{f"{path}__gte": start})
        if end:
            q &= Q(**{f"{path}__lte": end})
        return qs.filter(q)
    return qs


def _resolve_value(obj, path):
    cur = obj
    for part in path.split("__"):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    if isinstance(cur, Decimal):
        return float(cur)
    if hasattr(cur, "isoformat"):
        try:
            return cur.isoformat()
        except Exception:
            return str(cur)
    return cur


def apply_definition(qs, meta, *, field_keys, filters, group_by="", sort_by="", sort_dir="desc"):
    fmap = _field_map(meta)
    for filt in filters or []:
        key = filt.get("field_key") or filt.get("key")
        spec = fmap.get(key)
        if not spec:
            continue
        qs = _apply_filter(
            qs,
            spec["path"],
            filt.get("operator") or "eq",
            filt.get("value"),
            spec.get("type"),
        )

    # Grouping → values annotate
    if group_by and group_by in fmap:
        gpath = fmap[group_by]["path"]
        numeric_keys = [
            k
            for k in field_keys
            if k in fmap and fmap[k]["type"] == "number" and k != group_by
        ]
        annotations = {}
        for k in numeric_keys:
            annotations[k] = Sum(fmap[k]["path"])
        if not annotations:
            annotations["row_count"] = Count("id")
        qs = qs.values(gpath).annotate(**annotations).order_by()
        # Remap for serialization
        return "grouped", qs, gpath, list(annotations.keys())

    sort_key = sort_by if sort_by in fmap else (meta.get("default_sort") or "")
    if sort_key and sort_key in fmap:
        prefix = "-" if str(sort_dir).lower() != "asc" else ""
        qs = qs.order_by(f"{prefix}{fmap[sort_key]['path']}")
    return "rows", qs, None, field_keys


def run_report_definition(
    *,
    datasource,
    organization,
    field_keys=None,
    filters=None,
    group_by="",
    sort_by="",
    sort_dir="desc",
    limit=500,
    request=None,
    profile=None,
    view_mode="organization",
):
    meta = get_datasource(datasource)
    if not meta:
        raise ValueError("Unknown datasource")
    field_keys = list(field_keys or meta["default_fields"])
    fmap = _field_map(meta)
    field_keys = [k for k in field_keys if k in fmap]
    if not field_keys:
        field_keys = list(meta["default_fields"])

    qs = _base_queryset(
        datasource, organization, request=request, profile=profile, view_mode=view_mode
    )
    mode, qs, gpath, keys = apply_definition(
        qs,
        meta,
        field_keys=field_keys,
        filters=filters or [],
        group_by=group_by or "",
        sort_by=sort_by or "",
        sort_dir=sort_dir or "desc",
    )

    columns = []
    if mode == "grouped":
        columns.append({"key": group_by, "label": fmap[group_by]["label"], "type": "string"})
        for k in keys:
            if k == "row_count":
                columns.append({"key": "row_count", "label": "Count", "type": "number"})
            elif k in fmap:
                columns.append({"key": k, "label": fmap[k]["label"], "type": "number"})
        rows = []
        for item in qs[:limit]:
            row = {group_by: item.get(gpath)}
            for k in keys:
                val = item.get(k)
                if isinstance(val, Decimal):
                    val = float(val)
                row[k] = val
            rows.append(row)
    else:
        columns = [
            {"key": k, "label": fmap[k]["label"], "type": fmap[k]["type"]}
            for k in field_keys
            if k in fmap
        ]
        rows = []
        for obj in qs[:limit]:
            row = {}
            for k in field_keys:
                if k not in fmap:
                    continue
                row[k] = _resolve_value(obj, fmap[k]["path"])
            rows.append(row)

    return {
        "datasource": datasource,
        "columns": columns,
        "rows": rows,
        "count": len(rows),
        "truncated": len(rows) >= limit,
        "generated_at": timezone.now().isoformat(),
        "mode": mode,
    }


def run_saved_report(report, *, request=None, profile=None, view_mode="organization", limit=500):
    field_keys = list(report.fields.order_by("display_order").values_list("field_key", flat=True))
    filters = [
        {"field_key": f.field_key, "operator": f.operator, "value": f.value}
        for f in report.filters.all()
    ]
    return run_report_definition(
        datasource=report.report_type,
        organization=report.organization,
        field_keys=field_keys,
        filters=filters,
        group_by=report.group_by or "",
        sort_by=report.sort_by or "",
        sort_dir=report.sort_dir or "desc",
        limit=limit,
        request=request,
        profile=profile,
        view_mode=view_mode,
    )


def rows_to_csv(result):
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    cols = [c["key"] for c in result.get("columns") or []]
    labels = [c["label"] for c in result.get("columns") or []]
    writer.writerow(labels)
    for row in result.get("rows") or []:
        writer.writerow([row.get(c, "") for c in cols])
    return buffer.getvalue()
