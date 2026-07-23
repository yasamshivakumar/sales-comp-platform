import { useCallback, useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import api, { getApiErrorMessage } from "../../api";
import { useToast } from "../../Components/Toast";
import LoadingCenter from "../../Components/LoadingCenter";

function HistoryTab() {
  const { plan } = useOutletContext();
  const { error } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!plan?.id) return;
    setLoading(true);
    try {
      const res = await api.get(`compensation-plans/${plan.id}/activity/?limit=100`);
      setRows(res.data?.results || []);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load history"));
    } finally {
      setLoading(false);
    }
  }, [plan?.id, error]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingCenter minHeight={180} />;

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <h2 className="panel__title">History</h2>
        <p className="cp-tab-lead">
          Audit trail for this plan: creates, publishes, clones, and archives.
        </p>
        {rows.length === 0 ? (
          <div className="cp-empty-inline">
            <p>No history yet</p>
            <p className="cp-tab-lead">Actions on this plan will appear here.</p>
          </div>
        ) : (
          <ul className="cp-activity cp-activity--full">
            {rows.map((row) => (
              <li key={row.id} className="cp-activity__item">
                <strong>{row.label}</strong>
                <span>
                  {row.user_email || "system"}
                  {row.version_number != null ? ` · v${row.version_number}` : ""}
                </span>
                <time dateTime={row.created_at}>
                  {row.created_at ? new Date(row.created_at).toLocaleString() : ""}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default HistoryTab;
