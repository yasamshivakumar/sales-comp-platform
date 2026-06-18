import { useState, useEffect } from "react";
import api from "../api";
import PageHeader from "../Components/PageHeader";
import "../Components/enterprise.css";

function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const response = await api.get("audit-logs/?limit=200");
        setLogs(response.data.results || []);
      } catch (err) {
        setError(err.response?.data?.error || "Unable to load audit logs.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div>
      <PageHeader badge="Compliance" title="Audit log" />

      <div className="panel">
        {loading && <p>Loading audit events…</p>}
        {error && <p className="banner">{error}</p>}
        {!loading && !error && (
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
                    <td><code>{log.action}</code></td>
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
