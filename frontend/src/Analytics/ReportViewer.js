import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { formatMoney } from "../utils/currency";
import "./analytics.css";

function ReportViewer() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const run = await api.post(`analytics/reports/${id}/run/`, { limit: 500 });
      setReport(run.data.report);
      setResult(run.data.result);
    } catch (err) {
      setError(getApiErrorMessage(err, "Unable to run report"));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = async () => {
    const res = await api.get(`analytics/reports/${id}/export/`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(report?.name || "report").replace(/\s+/g, "-")}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const chartData = useMemo(() => {
    if (!result?.rows?.length || !result.columns?.length) return null;
    const numeric = (result.columns || []).filter((c) => c.type === "number");
    const labelCol = (result.columns || []).find((c) => c.type !== "number") || result.columns[0];
    const valueCol = numeric[0];
    if (!labelCol || !valueCol) return null;
    return result.rows.slice(0, 12).map((r) => ({
      label: String(r[labelCol.key] ?? ""),
      value: Number(r[valueCol.key] || 0),
    }));
  }, [result]);

  const maxVal = Math.max(...(chartData || []).map((d) => d.value), 1);

  return (
    <div className="an-panel">
      <div className="an-toolbar">
        <button type="button" className="an-btn" onClick={() => navigate("/analytics/reports")}>
          Back
        </button>
        <button type="button" className="an-btn" onClick={() => navigate(`/analytics/builder?id=${id}`)}>
          Edit
        </button>
        <button type="button" className="an-btn an-btn--primary" onClick={exportCsv} disabled={!report}>
          Export CSV
        </button>
        <button type="button" className="an-btn" onClick={load} disabled={loading}>
          {loading ? "Running..." : "Re-run"}
        </button>
      </div>
      {error ? <div className="an-error">{error}</div> : null}
      {report ? (
        <div className="an-viewer-head">
          <h2>{report.name}</h2>
          <p className="an-muted">
            {report.report_type_label} · {report.visualization} · {result?.count ?? 0} rows
          </p>
        </div>
      ) : null}

      {report?.visualization !== "table" && chartData ? (
        <div className="an-chart">
          {chartData.map((d) => (
            <div key={d.label} className="an-bar-row">
              <span className="an-bar-label">{d.label || "-"}</span>
              <div className="an-bar-track">
                <div
                  className="an-bar-fill"
                  style={{ width: `${Math.round((d.value / maxVal) * 100)}%` }}
                />
              </div>
              <span className="an-bar-value">{formatMoney(d.value, "INR", { compact: true })}</span>
            </div>
          ))}
        </div>
      ) : null}

      {result?.columns ? (
        <div className="an-table-wrap">
          <table className="an-table">
            <thead>
              <tr>
                {result.columns.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(result.rows || []).map((row, idx) => (
                <tr key={idx}>
                  {result.columns.map((c) => (
                    <td key={c.key}>
                      {c.type === "number" && row[c.key] != null
                        ? formatMoney(row[c.key], "INR", { compact: true })
                        : row[c.key] ?? "-"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export default ReportViewer;
