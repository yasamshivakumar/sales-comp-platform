import { useState, useEffect, useCallback } from "react";
import api, { getApiErrorMessage } from "../api";
import PageHeader from "../Components/PageHeader";
import "../Components/enterprise.css";

const ACTION_LABELS = {
  login_success: "Signed in",
  login_failed: "Failed sign-in",
  login_locked_out: "Login locked out",
  logout: "Signed out",
  invite_accepted: "Invite accepted",
  compensation_plan_created: "Compensation plan created",
  compensation_plan_updated: "Compensation plan updated",
  compensation_tier_created: "Compensation tier created",
  user_setup_created: "User setup created",
  user_setup_updated: "User setup updated",
  user_setup_upload: "User setup CSV uploaded",
  user_setup_upload_queued: "User setup CSV queued",
  orders_upload: "Orders CSV uploaded",
  order_created: "Order created",
  order_updated: "Order updated",
  hierarchy_created: "Hierarchy link created",
  "plan_version.clone": "Plan version cloned",
  "plan_version.publish": "Plan version published",
  "plan_version.archive": "Plan version archived",
  plan_version_cloned: "Plan version cloned",
  plan_version_published: "Plan version published",
  plan_version_archived: "Plan version archived",
  commissions_recalculated: "Commissions recalculated",
  commissions_manager_approved: "Manager approved commissions",
  commissions_finance_approved: "Finance approved commissions",
  commissions_approved: "Commissions approved",
  commission_dispute_opened: "Dispute opened",
  commission_dispute_resolved: "Dispute resolved",
  commission_dispute_acknowledged: "Dispute acknowledged",
  territory_created: "Territory created",
  territory_updated: "Territory updated",
  territory_deleted: "Territory deleted",
  payout_run_created: "Payout run created",
  payout_run_paid: "Payout run marked paid",
  integration_created: "Integration created",
  integration_updated: "Integration updated",
};

function formatAction(action) {
  if (!action) return "—";
  return ACTION_LABELS[action] || action.replace(/[_.]/g, " ");
}

function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("audit-logs/?limit=200");
      setLogs(response.data.results || []);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to load audit logs."));
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader badge="Compliance" title="Audit log">
        <button type="button" className="btn btn--secondary" onClick={load} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </PageHeader>

      <div className="panel">
        {loading && <p>Loading audit events…</p>}
        {error && <p className="banner">{error}</p>}
        {!loading && !error && logs.length === 0 && (
          <p style={{ color: "var(--text-muted)", margin: 0 }}>
            No audit events yet for your organization. Sign-ins, plan changes, user setup,
            orders, and approvals will appear here.
          </p>
        )}
        {!loading && !error && logs.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Details</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.user_email || "—"}</td>
                    <td>
                      <code title={log.action}>{formatAction(log.action)}</code>
                    </td>
                    <td>
                      <pre style={{ margin: 0, fontSize: "0.75rem", whiteSpace: "pre-wrap" }}>
                        {JSON.stringify(log.detail || {}, null, 0)}
                      </pre>
                    </td>
                    <td>{log.ip_address || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuditLogs;
