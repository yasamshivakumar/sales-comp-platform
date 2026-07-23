import { useState, useEffect, useCallback } from "react";
import api, { getApiErrorMessage } from "../api";
import PageHeader from "../Components/PageHeader";
import "../Components/enterprise.css";
import "./ActivityCenter.css";

const SEVERITY_OPTIONS = [
  { value: "", label: "All severities" },
  { value: "info", label: "Information" },
  { value: "success", label: "Success" },
  { value: "warning", label: "Warning" },
  { value: "critical", label: "Critical" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "success", label: "Success" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const SOURCE_OPTIONS = [
  { value: "", label: "All sources" },
  { value: "web", label: "Web" },
  { value: "api", label: "API" },
  { value: "csv_import", label: "CSV Import" },
  { value: "crm_sync", label: "CRM Sync" },
  { value: "background_job", label: "Background Job" },
];

const MODULE_OPTIONS = [
  { value: "", label: "All modules" },
  { value: "authentication", label: "Authentication" },
  { value: "people_access", label: "People & Access" },
  { value: "orders", label: "Orders" },
  { value: "commissions", label: "Commissions" },
  { value: "payouts", label: "Payouts" },
  { value: "compensation_plans", label: "Compensation Plans" },
  { value: "crm_integrations", label: "CRM Integrations" },
  { value: "payroll", label: "Payroll" },
  { value: "reports", label: "Reports" },
  { value: "roles_permissions", label: "Roles & Permissions" },
  { value: "audit_log", label: "Audit Log" },
  { value: "organization_settings", label: "Organization Settings" },
];

const ICON_MAP = {
  login: "🔑",
  export: "📤",
  import: "📥",
  approval: "✅",
  edit: "✏️",
  delete: "🗑️",
  calculation: "🧮",
  crm: "☁️",
  payroll: "💵",
  security: "🛡️",
};

function iconFor(row) {
  return ICON_MAP[row.icon] || ICON_MAP.edit;
}

function formatValue(v) {
  if (v === null || v === undefined || v === "") return "-";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

const emptyFilters = {
  date_from: "",
  date_to: "",
  module: "",
  user: "",
  role: "",
  severity: "",
  status: "",
  source: "",
  action: "",
  entity_type: "",
  business_unit: "",
  q: "",
};

function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [applied, setApplied] = useState(emptyFilters);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exportError, setExportError] = useState("");

  const queryString = useCallback(
    (extra = {}) => {
      const params = new URLSearchParams();
      params.set("page", String(extra.page ?? page));
      params.set("page_size", String(pageSize));
      Object.entries(applied).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      return params.toString();
    },
    [applied, page, pageSize]
  );

  const loadSummary = useCallback(async () => {
    try {
      const res = await api.get("audit-logs/summary/");
      setSummary(res.data);
    } catch {
      setSummary(null);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get(`audit-logs/?${queryString()}`);
      setLogs(response.data.results || []);
      setTotal(response.data.count || 0);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to load activity."));
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    api
      .get(`audit-logs/${selectedId}/`)
      .then((res) => {
        if (!cancelled) setDetail(res.data);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const applyFilters = (e) => {
    e?.preventDefault?.();
    setPage(1);
    setApplied({ ...filters });
  };

  const resetFilters = () => {
    setFilters(emptyFilters);
    setApplied(emptyFilters);
    setPage(1);
  };

  const exportCsv = async () => {
    setExportError("");
    try {
      const params = new URLSearchParams();
      Object.entries(applied).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      const res = await api.get(`audit-logs/export/?${params.toString()}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "activity-compliance-export.csv";
      a.click();
      window.URL.revokeObjectURL(url);
      loadSummary();
    } catch (err) {
      setExportError(
        getApiErrorMessage(err, "Export requires Admin or export_audit permission.")
      );
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const cards = [
    { key: "today_activities", label: "Today's Activities", value: summary?.today_activities },
    { key: "critical_events", label: "Critical Events", value: summary?.critical_events },
    { key: "security_events", label: "Security Events", value: summary?.security_events },
    { key: "failed_actions", label: "Failed Actions", value: summary?.failed_actions },
    { key: "exports", label: "Exports", value: summary?.exports },
    { key: "crm_syncs", label: "CRM Syncs", value: summary?.crm_syncs },
    { key: "payroll_runs", label: "Payroll Runs", value: summary?.payroll_runs },
  ];

  return (
    <div className="activity-center">
      <PageHeader badge="Compliance" title="Activity & Compliance">
        <button type="button" className="btn btn--secondary" onClick={load} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
        <button type="button" className="btn btn--secondary" onClick={exportCsv}>
          Export CSV
        </button>
      </PageHeader>

      {exportError && <p className="banner">{exportError}</p>}

      <div className="activity-summary">
        {cards.map((c) => (
          <div key={c.key} className="activity-summary__card">
            <div className="activity-summary__label">{c.label}</div>
            <div className="activity-summary__value">
              {c.value === undefined || c.value === null ? "-" : c.value}
            </div>
          </div>
        ))}
      </div>

      <form className="activity-filters" onSubmit={applyFilters}>
        <label>
          From
          <input
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
          />
        </label>
        <label>
          Module
          <select
            value={filters.module}
            onChange={(e) => setFilters((f) => ({ ...f, module: e.target.value }))}
          >
            {MODULE_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Severity
          <select
            value={filters.severity}
            onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value }))}
          >
            {SEVERITY_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Source
          <select
            value={filters.source}
            onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value }))}
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          User
          <input
            type="text"
            placeholder="email"
            value={filters.user}
            onChange={(e) => setFilters((f) => ({ ...f, user: e.target.value }))}
          />
        </label>
        <label className="activity-filters__search">
          Search
          <input
            type="search"
            placeholder="User, order, plan, employee, IP, correlation ID"
            value={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
          />
        </label>
        <div className="activity-filters__actions">
          <button type="submit" className="btn btn--primary">
            Apply
          </button>
          <button type="button" className="btn btn--secondary" onClick={resetFilters}>
            Reset
          </button>
        </div>
      </form>

      <div className="panel activity-panel">
        {loading && <p>Loading activity...</p>}
        {error && <p className="banner">{error}</p>}
        {!loading && !error && logs.length === 0 && (
          <p style={{ color: "var(--text-muted)", margin: 0 }}>
            No activity matches these filters. Sign-ins, plan changes, imports, and approvals
            appear here.
          </p>
        )}

        {!loading && !error && logs.length > 0 && (
          <div className="enterprise-table-wrap">
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>User</th>
                  <th>Module</th>
                  <th>Action</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="activity-row"
                    onClick={() => setSelectedId(log.id)}
                  >
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.user_email || "-"}</td>
                    <td>{log.module || "-"}</td>
                    <td>
                      <span className="activity-action-cell">
                        <span aria-hidden>{iconFor(log)}</span>
                        {log.action_label || log.action}
                      </span>
                    </td>
                    <td>
                      <span className={`sev-pill sev-pill--${log.severity}`}>{log.severity}</span>
                    </td>
                    <td>{log.status}</td>
                    <td>{log.source}</td>
                    <td>{log.ip_address || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > pageSize && (
          <div className="activity-pagination">
            <button
              type="button"
              className="btn btn--secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <span>
              Page {page} of {totalPages} ({total} events)
            </span>
            <button
              type="button"
              className="btn btn--secondary"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </div>

      {selectedId && (
        <div className="activity-drawer-backdrop" onClick={() => setSelectedId(null)}>
          <aside
            className="activity-drawer"
            onClick={(e) => e.stopPropagation()}
            aria-label="Activity detail"
          >
            <div className="activity-drawer__header">
              <h2>Activity detail</h2>
              <button type="button" className="btn btn--secondary" onClick={() => setSelectedId(null)}>
                Close
              </button>
            </div>
            {detailLoading && <p>Loading...</p>}
            {!detailLoading && detail && (
              <div className="activity-drawer__body">
                <section>
                  <h3>Who</h3>
                  <dl className="activity-dl">
                    <div>
                      <dt>User</dt>
                      <dd>{detail.user_email || "-"}</dd>
                    </div>
                    <div>
                      <dt>Employee ID</dt>
                      <dd>{detail.employee_id || "-"}</dd>
                    </div>
                    <div>
                      <dt>Role</dt>
                      <dd>{detail.role || "-"}</dd>
                    </div>
                  </dl>
                </section>
                <section>
                  <h3>What</h3>
                  <dl className="activity-dl">
                    <div>
                      <dt>Action</dt>
                      <dd>
                        {iconFor(detail)} {detail.action_label || detail.action}
                      </dd>
                    </div>
                    <div>
                      <dt>Module</dt>
                      <dd>{detail.module || "-"}</dd>
                    </div>
                    <div>
                      <dt>Entity</dt>
                      <dd>
                        {detail.entity_type || "-"}
                        {detail.entity_id ? ` #${detail.entity_id}` : ""}
                      </dd>
                    </div>
                  </dl>
                </section>
                <section>
                  <h3>When / Where</h3>
                  <dl className="activity-dl">
                    <div>
                      <dt>When</dt>
                      <dd>{new Date(detail.created_at).toLocaleString()}</dd>
                    </div>
                    <div>
                      <dt>IP</dt>
                      <dd>{detail.ip_address || "-"}</dd>
                    </div>
                    <div>
                      <dt>Browser / Device</dt>
                      <dd>{detail.browser || detail.device || "-"}</dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd>{detail.source}</dd>
                    </div>
                    <div>
                      <dt>Session ID</dt>
                      <dd className="mono">{detail.session_id || "-"}</dd>
                    </div>
                    <div>
                      <dt>Correlation ID</dt>
                      <dd className="mono">{detail.correlation_id || detail.request_id || "-"}</dd>
                    </div>
                  </dl>
                </section>
                <section>
                  <h3>Why</h3>
                  <p>{detail.reason || "-"}</p>
                </section>
                <section>
                  <h3>Changed fields</h3>
                  {(detail.changed_fields || []).length === 0 ? (
                    <p style={{ color: "var(--text-muted)" }}>No field-level changes recorded.</p>
                  ) : (
                    <table className="enterprise-table">
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th>Before</th>
                          <th>After</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(detail.changed_fields || []).map((field) => (
                          <tr key={field}>
                            <td>{field}</td>
                            <td>{formatValue((detail.old_value || {})[field])}</td>
                            <td>{formatValue((detail.new_value || {})[field])}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </section>
                <section>
                  <h3>Related</h3>
                  <dl className="activity-dl">
                    <div>
                      <dt>Plan</dt>
                      <dd>{detail.related?.plan_id || "-"}</dd>
                    </div>
                    <div>
                      <dt>Order</dt>
                      <dd>{detail.related?.order_id || "-"}</dd>
                    </div>
                    <div>
                      <dt>User profile</dt>
                      <dd>{detail.related?.profile_id || "-"}</dd>
                    </div>
                  </dl>
                </section>
                <section>
                  <h3>JSON payload</h3>
                  <pre className="activity-json">{JSON.stringify(detail.detail || {}, null, 2)}</pre>
                </section>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

export default AuditLogs;
