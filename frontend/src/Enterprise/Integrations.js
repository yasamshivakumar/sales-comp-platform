import { useState, useEffect } from "react";
import api, { getApiErrorMessage } from "../api";
import PageHeader from "../Components/PageHeader";
import "../Components/enterprise.css";

const CREDENTIAL_FIELDS = {
  salesforce: [
    { key: "instance_url", label: "Instance URL", placeholder: "https://yourorg.my.salesforce.com" },
    { key: "access_token", label: "Access token (optional if using OAuth below)", type: "password" },
    { key: "client_id", label: "Connected App Client ID" },
    { key: "client_secret", label: "Client Secret", type: "password" },
    { key: "username", label: "Username" },
    { key: "password", label: "Password", type: "password" },
    { key: "security_token", label: "Security token", type: "password" },
  ],
  generic_rest: [
    { key: "access_token", label: "Bearer token / API key", type: "password" },
    { key: "auth_type", label: "Auth type (bearer or api_key_header)" },
    { key: "api_key_header", label: "API key header name (if api_key_header)" },
  ],
  webhook: [],
  hubspot: [
    { key: "access_token", label: "Private app access token", type: "password" },
    { key: "auth_type", label: "Auth type", placeholder: "bearer" },
  ],
};

function Integrations({ embedded = false, inline = false, onClose, onOrdersSynced }) {
  const [providers, setProviders] = useState([]);
  const [defaultConfig, setDefaultConfig] = useState({});
  const [integrations, setIntegrations] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [syncedUsers, setSyncedUsers] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    name: "",
    provider: "salesforce",
    is_active: true,
    auto_sync_enabled: false,
    auto_sync_interval_minutes: 15,
    credentials: {},
    configText: "",
  });

  const loadAll = async () => {
    setLoading(true);
    try {
      const [provRes, intRes] = await Promise.all([
        api.get("integrations/providers/"),
        api.get("integrations/"),
      ]);
      setProviders(provRes.data.providers || []);
      setDefaultConfig(provRes.data.default_config || {});
      setIntegrations(intRes.data || []);
    } catch (err) {
      setMessage(err.response?.data?.error || "Failed to load integrations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const loadLogs = async (id) => {
    try {
      const res = await api.get(`integrations/${id}/sync-logs/`);
      setLogs(res.data || []);
    } catch {
      setLogs([]);
    }
  };

  const loadSyncedUsers = async (id) => {
    try {
      const res = await api.get(`integrations/${id}/synced-users/`);
      setSyncedUsers(res.data?.users || []);
    } catch {
      setSyncedUsers([]);
    }
  };

  const selectIntegration = async (item) => {
    setSelectedId(item.id);
    try {
      const res = await api.get(`integrations/${item.id}/`);
      const detail = res.data;
      setForm({
        name: detail.name,
        provider: detail.provider,
        is_active: detail.is_active,
        auto_sync_enabled: Boolean(detail.auto_sync_enabled),
        auto_sync_interval_minutes: detail.auto_sync_interval_minutes || 15,
        credentials: {},
        configText: JSON.stringify(detail.config || {}, null, 2),
      });
      if (detail.webhook_urls) {
        setIntegrations((current) =>
          current.map((row) =>
            row.id === item.id ? { ...row, webhook_urls: detail.webhook_urls } : row
          )
        );
      }
    } catch {
      setForm({
        name: item.name,
        provider: item.provider,
        is_active: item.is_active,
        auto_sync_enabled: Boolean(item.auto_sync_enabled),
        auto_sync_interval_minutes: item.auto_sync_interval_minutes || 15,
        credentials: {},
        configText: JSON.stringify(item.config || {}, null, 2),
      });
    }
    loadLogs(item.id);
    loadSyncedUsers(item.id);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setMessage("");
    try {
      if (form.provider === "hubspot" && !form.credentials.access_token?.trim()) {
        setMessage("HubSpot private app access token is required.");
        return;
      }
      let config = defaultConfig[form.provider] || {};
      if (form.configText.trim()) {
        config = JSON.parse(form.configText);
      }
      await api.post("integrations/", {
        name: form.name,
        provider: form.provider,
        is_active: form.is_active,
        auto_sync_enabled: form.auto_sync_enabled,
        auto_sync_interval_minutes: form.auto_sync_interval_minutes,
        credentials: form.credentials,
        config,
      });
      setMessage("Integration created.");
      setForm({ name: "", provider: form.provider, is_active: true, credentials: {}, configText: "" });
      loadAll();
    } catch (err) {
      setMessage(getApiErrorMessage(err, "Create failed."));
    }
  };

  const saveCredentialsIfNeeded = async () => {
    if (!selectedId) return;
    const hasCredentials = Object.keys(form.credentials).some((k) => form.credentials[k]?.trim());
    if (!hasCredentials) return;
    await api.patch(`integrations/${selectedId}/`, { credentials: form.credentials });
  };

  const handleUpdate = async () => {
    if (!selectedId) return;
    setMessage("");
    try {
      const payload = {
        name: form.name,
        is_active: form.is_active,
        auto_sync_enabled: form.auto_sync_enabled,
        auto_sync_interval_minutes: Number(form.auto_sync_interval_minutes) || 15,
      };
      if (Object.keys(form.credentials).some((k) => form.credentials[k])) {
        payload.credentials = form.credentials;
      }
      if (form.configText.trim()) {
        payload.config = JSON.parse(form.configText);
      }
      await api.patch(`integrations/${selectedId}/`, payload);
      setMessage("Integration updated.");
      loadAll();
    } catch (err) {
      setMessage(getApiErrorMessage(err, "Update failed."));
    }
  };

  const formatSyncResult = (result) => {
    if (!result) return "Sync done.";
    const skipped = result.skipped ?? result.skipped_orders?.length ?? 0;
    const unresolved = result.unresolved_orders?.length ?? 0;
    const commissionsCreated = result.commissions_created ?? 0;
    const commissionsSkipped = result.commissions_skipped ?? 0;
    let text =
      `Sync done: ${result.success ?? 0} succeeded, ${result.failed ?? 0} failed`;
    if (skipped) text += `, ${skipped} skipped (archived CRM owners)`;
    if (unresolved) text += `, ${unresolved} unresolved owner mapping(s)`;
    if (commissionsCreated || commissionsSkipped) {
      text += `. Commissions: ${commissionsCreated} created`;
      if (commissionsSkipped) {
        text += `, ${commissionsSkipped} skipped (check User Setup + compensation plan)`;
      }
    } else if (result.success > 0) {
      text += ". Closed-won CRM deals import as Success and calculate commissions when configured.";
    }
    return `${text}.`;
  };

  const runAction = async (action) => {
    if (!selectedId) return;
    setMessage("");
    const actionPath = String(action).replace(/^\/+|\/+$/g, "");
    try {
      await saveCredentialsIfNeeded();
      const res = await api.post(`integrations/${selectedId}/${actionPath}/`, {}, {
        timeout: actionPath.includes("sync") ? 120000 : 30000,
      });
      if (actionPath === "sync/full") {
        const users = res.data.users?.result;
        const orders = res.data.orders?.result;
        setMessage(
          `Full sync done. Users: ${users?.success ?? 0} ok. ${formatSyncResult(orders)}`
        );
      } else {
        setMessage(
          actionPath.includes("sync")
            ? formatSyncResult(res.data.result)
            : res.data.message || "OK"
        );
      }
      loadLogs(selectedId);
      loadSyncedUsers(selectedId);
      loadAll();
      if ((actionPath.includes("sync/orders") || actionPath === "sync/full") && onOrdersSynced) {
        onOrdersSynced(res.data);
      }
    } catch (err) {
      setMessage(getApiErrorMessage(err, "Action failed."));
    }
  };

  const selected = integrations.find((i) => i.id === selectedId);
  const selectedProviderMeta = providers.find((p) => p.id === selected?.provider);
  const credFields = CREDENTIAL_FIELDS[form.provider] || [];
  const latestUserLog = logs.find((log) => log.sync_type === "users");
  const lastSyncRecords = latestUserLog?.result?.records || [];
  const lastSyncFetched = latestUserLog?.result?.fetched || [];
  const userRows =
    lastSyncRecords.length > 0
      ? lastSyncRecords
      : lastSyncFetched.map((row, index) => ({
          row: index + 1,
          name: row.name,
          email: row.email,
          crm_user_id: row.crm_user_id,
          crm_alt_user_id: row.crm_alt_user_id,
          employee_id: "",
          status: "fetched",
        }));

  return (
    <div
      className={[
        embedded ? "integrations-panel integrations-panel--embedded" : "",
        inline ? "integrations-panel--orders" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {!embedded && (
        <PageHeader badge="Integrations" title="CRM & data connections" />
      )}
      {embedded && (
        <div className="integrations-panel__head">
          <div>
            <h2 id="integrations-dialog-title" className="integrations-panel__title">
              {inline ? "Connect CRM" : "CRM integrations"}
            </h2>
            <p className="integrations-panel__subtitle">
              Pull users and deals from HubSpot or Salesforce — same import pipeline as CSV uploads.
              Synced orders land in the Order queue as Booked; mark Success to calculate commissions.
            </p>
          </div>
          {onClose && (
            <button type="button" className="btn-secondary" onClick={onClose} aria-label="Close">
              ✕ Close
            </button>
          )}
        </div>
      )}

      {!embedded && (
      <div className="banner" style={{ marginBottom: "1rem" }}>
        Existing <strong>CSV uploads</strong> and manual entry are unchanged. Integrations add an optional sync path from CRM tools (Salesforce, HubSpot via REST, Zapier webhooks).
      </div>
      )}

      {message && <p className="banner">{message}</p>}

      <div className="panel" style={{ marginBottom: "1rem" }}>
        <h3 className="panel__title">Add connection</h3>
        <form onSubmit={handleCreate}>
          <div className="enterprise-form-row">
            <label>
              Name
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </label>
            <label>
              Provider
              <select
                className="input"
                value={form.provider}
                onChange={(e) =>
                  setForm({
                    ...form,
                    provider: e.target.value,
                    configText: JSON.stringify(defaultConfig[e.target.value] || {}, null, 2),
                  })
                }
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
          </div>

          {credFields.length > 0 && (
            <div className="enterprise-form-row">
              {credFields.map((field) => (
                <label key={field.key}>
                  {field.label}
                  <input
                    className="input"
                    type={field.type || "text"}
                    placeholder={field.placeholder || ""}
                    value={form.credentials[field.key] || ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        credentials: { ...form.credentials, [field.key]: e.target.value },
                      })
                    }
                  />
                </label>
              ))}
            </div>
          )}

          <label style={{ display: "block", marginBottom: "0.75rem" }}>
            Config (SOQL, URLs, field mappings) — JSON
            <textarea
              className="input"
              rows={10}
              style={{ width: "100%", fontFamily: "monospace", fontSize: "0.85rem" }}
              value={form.configText || JSON.stringify(defaultConfig[form.provider] || {}, null, 2)}
              onChange={(e) => setForm({ ...form, configText: e.target.value })}
            />
          </label>

          <button type="submit" className="btn-primary">Create integration</button>
        </form>
      </div>

      <div className="panel">
        <h3 className="panel__title">Connections</h3>
        {loading ? (
          <p>Loading…</p>
        ) : integrations.length === 0 ? (
          <p>No integrations yet.</p>
        ) : (
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Provider</th>
                <th>Status</th>
                <th>Last user sync</th>
                <th>Last order sync</th>
                <th>Auto</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {integrations.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.provider}</td>
                  <td>{item.is_active ? "Active" : "Inactive"}</td>
                  <td>{item.last_user_sync_at ? new Date(item.last_user_sync_at).toLocaleString() : "—"}</td>
                  <td>{item.last_order_sync_at ? new Date(item.last_order_sync_at).toLocaleString() : "—"}</td>
                  <td>{item.auto_sync_enabled ? `Every ${item.auto_sync_interval_minutes || 15}m` : "—"}</td>
                  <td>
                    <button type="button" className="btn-secondary" onClick={() => selectIntegration(item)}>
                      Manage
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="panel" style={{ marginTop: "1rem" }}>
          <h3 className="panel__title">Manage: {selected.name}</h3>
          {selected.provider === "hubspot" && (
            <p className="integrations-panel__subtitle" style={{ marginBottom: "0.75rem" }}>
              HubSpot automation: enable auto-sync below for periodic ingest, or register the
              webhook URL in HubSpot for real-time closed-won deals. New owners are imported
              automatically when deals reference them.
            </p>
          )}

          {selected.provider === "hubspot" && selected.webhook_urls?.events && (
            <div className="banner" style={{ marginBottom: "1rem" }}>
              <strong>HubSpot webhook URL</strong> (POST deal events — subscribe to{" "}
              <code>deal.creation</code> and <code>deal.propertyChange</code> for{" "}
              <code>dealstage</code>)
              <br />
              <code>{selected.webhook_urls.events}</code>
            </div>
          )}

          {selected.provider !== "webhook" && (
            <div className="enterprise-form-row" style={{ marginBottom: "1rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={form.auto_sync_enabled}
                  onChange={(e) =>
                    setForm({ ...form, auto_sync_enabled: e.target.checked })
                  }
                />
                Automatic sync (users → closed-won deals → commissions)
              </label>
              <label>
                Interval (minutes)
                <input
                  className="input"
                  type="number"
                  min={5}
                  max={1440}
                  value={form.auto_sync_interval_minutes}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      auto_sync_interval_minutes: e.target.value,
                    })
                  }
                  disabled={!form.auto_sync_enabled}
                />
              </label>
              {selected.last_auto_sync_at && (
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Last auto sync: {new Date(selected.last_auto_sync_at).toLocaleString()}
                </span>
              )}
            </div>
          )}

          {selected.provider !== "webhook" && (CREDENTIAL_FIELDS[selected.provider] || []).length > 0 && (
            <div className="enterprise-form-row">
              {CREDENTIAL_FIELDS[selected.provider].map((field) => (
                <label key={field.key}>
                  {field.label}
                  <input
                    className="input"
                    type={field.type || "text"}
                    placeholder={field.placeholder || "Paste to update saved credentials"}
                    value={form.credentials[field.key] || ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        credentials: { ...form.credentials, [field.key]: e.target.value },
                      })
                    }
                  />
                </label>
              ))}
            </div>
          )}

          {selected.provider === "webhook" && selected.webhook_urls && (
            <div className="banner" style={{ marginBottom: "1rem" }}>
              <strong>Webhook URLs</strong> (POST JSON from Zapier / Make / CRM)
              <br />
              Users: <code>{selected.webhook_urls.users}</code>
              <br />
              Orders: <code>{selected.webhook_urls.orders}</code>
            </div>
          )}

          <div className="enterprise-form-row">
            <button type="button" className="btn-secondary" onClick={() => runAction("test")}>
              Test connection
            </button>
            {selected.provider !== "webhook" && (
              <>
                {selectedProviderMeta?.supports_full_sync && (
                  <button type="button" className="btn-primary" onClick={() => runAction("sync/full")}>
                    Full sync (users → orders → commissions)
                  </button>
                )}
                <button type="button" className="btn-secondary" onClick={() => runAction("sync/users")}>
                  Sync users only
                </button>
                <button type="button" className="btn-secondary" onClick={() => runAction("sync/orders")}>
                  Sync orders only
                </button>
              </>
            )}
            <button type="button" className="btn-primary" onClick={handleUpdate}>
              Save changes
            </button>
          </div>

          {(selected.provider !== "webhook") && (
            <>
              <h4 style={{ marginTop: "1.25rem" }}>CRM-linked employees in Incentra</h4>
              {syncedUsers.length === 0 ? (
                <p style={{ color: "var(--text-muted)", marginBottom: "1rem" }}>
                  No CRM-linked employees yet. Run <strong>Sync users</strong> to import HubSpot owners.
                </p>
              ) : (
                <table className="enterprise-table" style={{ marginBottom: "1rem" }}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>CRM owner ID</th>
                      <th>CRM user ID</th>
                      <th>Employee ID</th>
                      <th>Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {syncedUsers.map((user) => (
                      <tr key={user.id}>
                        <td>{user.name || `${user.first_name || ""} ${user.last_name || ""}`.trim() || "—"}</td>
                        <td>{user.email}</td>
                        <td><code>{user.crm_user_id || "—"}</code></td>
                        <td><code>{user.crm_alt_user_id || "—"}</code></td>
                        <td><code>{user.employee_id || "—"}</code></td>
                        <td>{user.role || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {userRows.length > 0 ? (
                <>
                  <h4 style={{ marginTop: "0.5rem" }}>
                    Last user sync
                    {latestUserLog?.started_at
                      ? ` (${new Date(latestUserLog.started_at).toLocaleString()})`
                      : ""}
                  </h4>
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Name</th>
                        <th>Email</th>
                        <th>CRM owner ID</th>
                        <th>CRM user ID</th>
                        <th>Employee ID</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {userRows.map((row) => (
                        <tr key={`user-row-${row.row}-${row.email || row.crm_user_id}`}>
                          <td>{row.row}</td>
                          <td>{row.name || "—"}</td>
                          <td>{row.email || "—"}</td>
                          <td><code>{row.crm_user_id || "—"}</code></td>
                          <td><code>{row.crm_alt_user_id || "—"}</code></td>
                          <td><code>{row.employee_id || "—"}</code></td>
                          <td>
                            {row.status === "failed" ? (
                              <span style={{ color: "var(--warning-color)" }} title={row.error}>
                                failed{row.error ? `: ${row.error}` : ""}
                              </span>
                            ) : (
                              row.status || "—"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <p style={{ color: "var(--text-muted)" }}>
                  No user sync run yet for this connection.
                </p>
              )}
            </>
          )}

          {logs.length > 0 && (
            <>
              <h4 style={{ marginTop: "1rem" }}>Recent sync logs</h4>
              <table className="enterprise-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Fetched</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td>{new Date(log.started_at).toLocaleString()}</td>
                      <td>{log.sync_type}</td>
                      <td>{log.status}</td>
                      <td>{log.records_fetched}</td>
                      <td>
                        {log.result?.success != null
                          ? `${log.result.success} ok / ${log.result.failed} failed` +
                            (log.result.skipped ? ` / ${log.result.skipped} skipped` : "")
                          : log.error_message || "—"}
                        {log.result?.skipped_orders?.length > 0 && (
                          <div style={{ marginTop: "0.35rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                            {log.result.skipped_orders.map((item, idx) => (
                              <div key={`${log.id}-skip-${idx}`}>
                                Order {item.order_id || "—"}: {item.reason}
                                {item.owner_email ? ` (${item.owner_email})` : ""}
                              </div>
                            ))}
                          </div>
                        )}
                        {log.result?.errors?.length > 0 && (
                          <div style={{ marginTop: "0.35rem", fontSize: "0.85rem", color: "var(--warning-color)" }}>
                            {log.result.errors.map((item, idx) => (
                              <div key={`${log.id}-err-${idx}`}>
                                Row {item.row}
                                {item.email ? ` (${item.email})` : ""}: {item.error}
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default Integrations;
