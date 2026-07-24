import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import "./analytics.css";

function ScheduledReports() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("analytics/schedules/");
      setRows(res.data.results || []);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to load schedules"));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const deactivate = async (id) => {
    try {
      await api.delete(`analytics/schedules/${id}/`);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to deactivate"));
    }
  };

  return (
    <div className="an-panel">
      <div className="an-toolbar">
        <p className="an-muted" style={{ margin: 0 }}>
          Schedules deliver CSV/Excel by email on the chosen cadence (worker runs next_run_at).
        </p>
        <Link className="an-btn an-btn--primary" to="/analytics/reports">
          Schedule from library
        </Link>
        <button type="button" className="an-btn" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>
      {error ? <div className="an-error">{error}</div> : null}
      {!loading && rows.length === 0 ? (
        <p className="an-muted">No active schedules. Use Schedule on a report in the library.</p>
      ) : (
        <div className="an-table-wrap">
          <table className="an-table">
            <thead>
              <tr>
                <th>Report</th>
                <th>Frequency</th>
                <th>Delivery</th>
                <th>Recipients</th>
                <th>Next run</th>
                <th>Last run</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={`/analytics/reports/${s.report_id}`}>{s.report_name}</Link>
                  </td>
                  <td>{s.frequency}</td>
                  <td>{s.delivery}</td>
                  <td>{(s.recipients || []).join(", ") || "-"}</td>
                  <td>{s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "-"}</td>
                  <td>{s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "Never"}</td>
                  <td>
                    <button type="button" className="an-danger" onClick={() => deactivate(s.id)}>
                      Deactivate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ScheduledReports;
