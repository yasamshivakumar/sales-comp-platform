import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import api, { getApiErrorMessage, getAuthToken } from "../../api";
import { useToast } from "../../Components/Toast";
import "../../Documents/documents.css";

function statusBadge(status) {
  const label = (status || "—").replace(/_/g, " ");
  return <span className={`cdr-badge status-${status || "draft"}`}>{label}</span>;
}

function DocumentsTab() {
  const { plan } = useOutletContext();
  const { error } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!plan?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`compensation-plans/${plan.id}/documents/`);
      setRows(res.data?.results || []);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load plan documents"));
    } finally {
      setLoading(false);
    }
  }, [plan?.id, error]);

  useEffect(() => {
    load();
  }, [load]);

  const download = async (docId, fileName) => {
    const token = getAuthToken();
    const base = (api.defaults.baseURL || "/api/").replace(/\/?$/, "/");
    const res = await fetch(
      `${base}documents/${docId}/download/?reason=${encodeURIComponent("Plan document review")}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }
    );
    if (!res.ok) throw new Error("Download failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName || "document.pdf";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <p className="cdr-muted">Loading documents…</p>;

  return (
    <div className="cdr-plan-docs">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          <h3 style={{ margin: "0 0 4px" }}>Related documents</h3>
          <p className="cdr-muted" style={{ margin: 0 }}>
            Compensation plans, policies, and approval evidence linked to this program.
          </p>
        </div>
        <Link className="pg-btn" to="/documents">
          Open Governance Center
        </Link>
      </div>
      {!rows.length ? (
        <div className="cdr-empty">
          <strong>No documents linked</strong>
          <p>
            Register documents in the Compensation Governance Center and relate them to this compensation
            plan.
          </p>
          <Link className="pg-btn pg-btn--primary" to="/documents">
            Go to Governance Center
          </Link>
        </div>
      ) : (
        rows.map((r) => (
          <article key={r.id} className="cdr-plan-docs__card">
            <div>
              <strong>
                <Link to={`/documents/${r.id}`} style={{ color: "inherit", textDecoration: "none" }}>
                  {r.name}
                </Link>
              </strong>
              <div className="cdr-plan-docs__meta">
                {statusBadge(r.status)}
                <span>
                  {r.version || "—"} · {r.document_type_label}
                  {r.effective_from || r.effective_to
                    ? ` · ${r.effective_from || "…"} – ${r.effective_to || "…"}`
                    : ""}
                </span>
              </div>
            </div>
            <button
              type="button"
              className="cdr-link"
              onClick={() => download(r.id, r.file_name || `${r.name}.pdf`)}
            >
              Download
            </button>
          </article>
        ))
      )}
    </div>
  );
}

export default DocumentsTab;
