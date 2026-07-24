import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import "./analytics.css";

function ReportLibrary({ mode = "all" }) {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [canBuild, setCanBuild] = useState(false);
  const isSaved = mode === "saved";

  useEffect(() => {
    let cancelled = false;
    api
      .get("user-profile/")
      .then((res) => {
        if (cancelled) return;
        const p = res.data || {};
        setCanBuild(Boolean(p.is_admin || p.is_finance || p.is_manager));
      })
      .catch(() => {
        if (!cancelled) setCanBuild(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (isSaved) params.set("mine", "1");
      const res = await api.get(`analytics/reports/?${params}`);
      setRows(res.data.results || []);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to load reports"));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [q, isSaved]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const duplicate = async (id) => {
    try {
      const res = await api.post(`analytics/reports/${id}/duplicate/`);
      navigate(`/analytics/builder?id=${res.data.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Duplicate failed"));
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Archive this report?")) return;
    try {
      await api.delete(`analytics/reports/${id}/`);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, "Delete failed"));
    }
  };

  const exportCsv = async (id, name) => {
    try {
      const res = await api.get(`analytics/reports/${id}/export/`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(name || "report").replace(/\s+/g, "-")}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiErrorMessage(err, "Export failed"));
    }
  };

  const schedule = async (id) => {
    const frequency = window.prompt("Frequency: daily, weekly, or monthly", "weekly");
    if (!frequency) return;
    const delivery = window.prompt(
      "Delivery: email_excel, email_pdf, or download",
      "email_excel"
    );
    if (!delivery) return;
    try {
      await api.post("analytics/schedules/", {
        report_id: id,
        frequency: frequency.trim().toLowerCase(),
        delivery: delivery.trim().toLowerCase(),
      });
      navigate("/analytics/schedules");
    } catch (err) {
      setError(getApiErrorMessage(err, "Schedule failed"));
    }
  };

  return (
    <div className="an-panel">
      <div className="an-toolbar">
        <input
          className="an-input"
          placeholder={isSaved ? "Search saved reports" : "Search reports"}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {canBuild ? (
          <Link className="an-btn an-btn--primary" to="/analytics/builder">
            New report
          </Link>
        ) : null}
        <button type="button" className="an-btn" onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
      {error ? <div className="an-error">{error}</div> : null}
      {!loading && rows.length === 0 ? (
        <p className="an-muted">
          {isSaved
            ? "You have no saved reports yet."
            : canBuild
              ? "No reports yet. Create one in Report Builder."
              : "No reports shared with you yet."}
        </p>
      ) : (
        <div className="an-table-wrap">
          <table className="an-table">
            <thead>
              <tr>
                <th>Report Name</th>
                <th>Type</th>
                <th>Created By</th>
                <th>Last Modified</th>
                <th>Owner</th>
                <th>Visibility</th>
                <th>Last Run</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.name}</strong>
                    {r.description ? <div className="an-subline">{r.description}</div> : null}
                  </td>
                  <td>{r.report_type_label || r.report_type}</td>
                  <td>{r.created_by_email || "-"}</td>
                  <td>{r.updated_at ? new Date(r.updated_at).toLocaleString() : "-"}</td>
                  <td>{r.owner_email || "-"}</td>
                  <td>{r.visibility}</td>
                  <td>{r.last_run_at ? new Date(r.last_run_at).toLocaleString() : "Never"}</td>
                  <td>
                    <div className="an-actions">
                      <button type="button" onClick={() => navigate(`/analytics/reports/${r.id}`)}>
                        Open
                      </button>
                      {canBuild ? (
                        <>
                          <button
                            type="button"
                            onClick={() => navigate(`/analytics/builder?id=${r.id}`)}
                          >
                            Edit
                          </button>
                          <button type="button" onClick={() => duplicate(r.id)}>
                            Duplicate
                          </button>
                          <button type="button" onClick={() => schedule(r.id)}>
                            Schedule
                          </button>
                        </>
                      ) : null}
                      <button type="button" onClick={() => exportCsv(r.id, r.name)}>
                        Export
                      </button>
                      {canBuild ? (
                        <button type="button" className="an-danger" onClick={() => remove(r.id)}>
                          Delete
                        </button>
                      ) : null}
                    </div>
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

export default ReportLibrary;
