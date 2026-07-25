import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import api, { getApiErrorMessage } from "../../api";
import { useToast } from "../../Components/Toast";
import LoadingCenter from "../../Components/LoadingCenter";

function formatDate(value) {
  if (!value) return "Open";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function statusTone(status) {
  if (status === "approved") return "success";
  if (status === "pending_approval" || status === "draft") return "warning";
  if (status === "rejected" || status === "revoked") return "danger";
  return "neutral";
}

function OverridesTab() {
  const { plan } = useOutletContext();
  const { error } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!plan?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`compensation-plans/${plan.id}/overrides/`);
      setData(res.data);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load override summary"));
    } finally {
      setLoading(false);
    }
  }, [plan?.id, error]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="cp-tab">
        <LoadingCenter label="Loading override summary…" />
      </div>
    );
  }

  const summary = data?.override_summary || {};
  const overrides = data?.overrides || [];

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <div className="cp-tab-panel__head">
          <div>
            <h2 className="panel__title">Employee Overrides</h2>
            <p className="cp-tab-panel__hint">
              Overrides are exceptions layered on this plan — they never replace it. Spot
              employees with custom terms without duplicating the plan.
            </p>
          </div>
        </div>

        <div className="cp-coverage-chips cp-override-stats">
          <span className="cp-chip">
            Employees using plan: <strong>{data?.employees_using_plan ?? 0}</strong>
          </span>
          <span className="cp-chip">
            With overrides: <strong>{data?.employees_with_overrides ?? 0}</strong>
          </span>
          <span className="cp-chip">
            Active: <strong>{summary.active ?? 0}</strong>
          </span>
          <span className="cp-chip">
            Pending: <strong>{summary.pending ?? 0}</strong>
          </span>
          <span className="cp-chip">
            Draft: <strong>{summary.draft ?? 0}</strong>
          </span>
          <span className="cp-chip">
            Expired: <strong>{summary.expired ?? 0}</strong>
          </span>
        </div>

        {(summary.by_type || []).length > 0 ? (
          <div className="cp-coverage-chips" style={{ marginTop: 10 }}>
            {(summary.by_type || []).map((row) => (
              <span key={row.type} className="cp-chip">
                {row.label}: <strong>{row.count}</strong>
              </span>
            ))}
          </div>
        ) : null}

        <h3 className="cp-section-title" style={{ marginTop: 20 }}>
          Employees with custom compensation
        </h3>

        {overrides.length === 0 ? (
          <div className="cp-empty-inline">
            <p>No employee overrides on this plan. Everyone receives the standard terms.</p>
          </div>
        ) : (
          <div className="enterprise-table-wrap">
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Override</th>
                  <th>Type</th>
                  <th>Value</th>
                  <th>Effective</th>
                  <th>Status</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {overrides.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link to={`/user-setup/${row.employee_id}/compensation`}>
                        {row.employee_name || row.employee_code || `#${row.employee_id}`}
                      </Link>
                      {row.employee_code ? (
                        <div className="cp-tab-panel__hint">{row.employee_code}</div>
                      ) : null}
                    </td>
                    <td>
                      <strong>{row.name}</strong>
                      {row.is_active_now ? (
                        <div className="cp-tab-panel__hint">Active now</div>
                      ) : null}
                    </td>
                    <td>{row.override_type_label}</td>
                    <td>
                      {row.value == null
                        ? "—"
                        : row.value_unit === "percent"
                          ? `${row.value}%`
                          : row.value}
                    </td>
                    <td>
                      {formatDate(row.effective_from)} – {formatDate(row.effective_to)}
                    </td>
                    <td>
                      <span className={`cp-override-status cp-override-status--${statusTone(row.status)}`}>
                        {(row.status || "").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td>{row.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default OverridesTab;
