import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import "./integrationCenter.css";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "connections", label: "Connections" },
  { id: "mapping", label: "Field Mapping" },
  { id: "history", label: "Sync History" },
  { id: "logs", label: "Logs" },
];

const AUTH_FIELDS = {
  salesforce: [
    { key: "instance_url", label: "Instance URL", placeholder: "https://yourorg.my.salesforce.com" },
    { key: "client_id", label: "Connected App Client ID" },
    { key: "client_secret", label: "Client Secret", type: "password" },
    { key: "username", label: "Username (password grant)" },
    { key: "password", label: "Password", type: "password" },
    { key: "security_token", label: "Security token", type: "password" },
    { key: "access_token", label: "Access token (optional)", type: "password" },
  ],
  hubspot: [
    { key: "access_token", label: "Private app access token", type: "password" },
  ],
};

function statusClass(status) {
  if (status === "connected") return "ic-badge--ok";
  if (status === "syncing") return "ic-badge--sync";
  if (status === "failed") return "ic-badge--err";
  if (status === "auth_expired") return "ic-badge--warn";
  return "ic-badge--muted";
}

function formatWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function ProviderCard({ provider, selected, onSelect, disabled }) {
  return (
    <button
      type="button"
      className={`ic-provider${selected ? " is-selected" : ""}${disabled ? " is-disabled" : ""}`}
      onClick={() => !disabled && onSelect(provider)}
      disabled={disabled}
    >
      <strong>{provider.name}</strong>
      <span>{provider.description}</span>
      {provider.coming_soon ? <em>Coming soon</em> : null}
    </button>
  );
}

function ConnectionWizard({ catalog, onClose, onCreated }) {
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [provider, setProvider] = useState(null);
  const [credentials, setCredentials] = useState({});
  const [authMethod, setAuthMethod] = useState("oauth");
  const [orgName, setOrgName] = useState("");
  const [objects, setObjects] = useState({
    users: true,
    deals: true,
    accounts: false,
    products: false,
  });
  const [mappings, setMappings] = useState([]);
  const [rules, setRules] = useState({
    closed_won_only: true,
    import_status: "Booked",
    commission_after_approval: true,
  });
  const [frequency, setFrequency] = useState("daily");
  const [preview, setPreview] = useState(null);
  const [createdId, setCreatedId] = useState(null);

  const providers = (catalog?.providers || []).filter(
    (p) => p.id === "salesforce" || p.id === "hubspot" || p.id === "dynamics"
  );

  useEffect(() => {
    if (!provider || !catalog) return;
    const defaults = catalog.default_config?.[provider.id] || {};
    const rows = [];
    const userMap = defaults.users?.field_map || {};
    Object.entries(userMap).forEach(([target, source]) => {
      rows.push({
        source_object: "users",
        source_field: String(source),
        target_field: target,
        is_required: ["email", "name", "crm_user_id"].includes(target),
      });
    });
    const orderMap = defaults.orders?.field_map || {};
    Object.entries(orderMap).forEach(([target, source]) => {
      rows.push({
        source_object: "deals",
        source_field: String(source),
        target_field: target,
        is_required: ["order_id", "sales_amount", "order_date", "crm_owner_id"].includes(
          target
        ),
      });
    });
    setMappings(rows);
  }, [provider, catalog]);

  const sourceFields = catalog?.source_fields?.[provider?.id] || {};
  const targetFields = catalog?.target_fields || {};

  const createDraft = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api.post("integrations/center/wizard/", {
        provider: provider.id,
        name: `${provider.name} — ${orgName || "Production"}`,
        auth_method: authMethod,
        credentials,
        connected_org_name: orgName,
        objects_enabled: objects,
        field_mappings: mappings,
        sync_rules: rules,
        sync_frequency: frequency,
      });
      setCreatedId(res.data.id);
      return res.data.id;
    } catch (err) {
      setError(getApiErrorMessage(err) || "Failed to create connection.");
      return null;
    } finally {
      setBusy(false);
    }
  };

  const loadPreview = async (id) => {
    setBusy(true);
    setError("");
    try {
      const res = await api.get(
        `integrations/center/${id}/preview/?resource=deals&limit=8`
      );
      setPreview(res.data);
    } catch (err) {
      setError(getApiErrorMessage(err) || "Preview failed — check authentication.");
      setPreview({ records: [], count: 0 });
    } finally {
      setBusy(false);
    }
  };

  const next = async () => {
    setError("");
    if (step === 1 && !provider) {
      setError("Select a CRM provider.");
      return;
    }
    if (step === 2) {
      const needToken = provider.id === "hubspot";
      if (needToken && !credentials.access_token) {
        setError("Access token is required.");
        return;
      }
      if (provider.id === "salesforce" && !credentials.instance_url) {
        setError("Salesforce instance URL is required.");
        return;
      }
      if (
        provider.id === "salesforce" &&
        !credentials.access_token &&
        !(credentials.client_id && credentials.username && credentials.password)
      ) {
        setError("Provide an access token or Connected App password-grant credentials.");
        return;
      }
    }
    if (step === 3 && !objects.users && !objects.deals) {
      setError("Select at least People or Deals to continue.");
      return;
    }
    if (step === 4) {
      const requiredMissing = [];
      if (objects.users) {
        ["email", "name", "crm_user_id"].forEach((field) => {
          const row = mappings.find((m) => m.source_object === "users" && m.target_field === field);
          if (!row?.source_field) requiredMissing.push(`People → ${field}`);
        });
      }
      if (objects.deals) {
        ["order_id", "sales_amount", "order_date", "crm_owner_id"].forEach((field) => {
          const row = mappings.find((m) => m.source_object === "deals" && m.target_field === field);
          if (!row?.source_field) requiredMissing.push(`Deals → ${field}`);
        });
      }
      if (requiredMissing.length) {
        setError(`Complete required mappings: ${requiredMissing.join(", ")}`);
        return;
      }
    }
    if (step === 5) {
      const id = createdId || (await createDraft());
      if (!id) return;
      await loadPreview(id);
      setStep(6);
      return;
    }
    if (step === 6) {
      onCreated();
      onClose();
      return;
    }
    setStep((s) => s + 1);
  };

  return (
    <div className="ic-modal" role="dialog" aria-modal="true">
      <button type="button" className="ic-modal__backdrop" onClick={onClose} aria-label="Close" />
      <div className="ic-modal__panel">
        <header className="ic-modal__head">
          <div>
            <p className="ic-eyebrow">Connection wizard</p>
            <h2>Connect CRM</h2>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </header>

        <ol className="ic-steps">
          {["CRM", "Auth", "Objects", "Mapping", "Rules", "Preview"].map((label, idx) => (
            <li key={label} className={step === idx + 1 ? "is-active" : step > idx + 1 ? "is-done" : ""}>
              <span className="ic-steps__num">{idx + 1}</span>
              <span className="ic-steps__label">{label}</span>
            </li>
          ))}
        </ol>

        {error ? <p className="ic-error">{error}</p> : null}

        {step === 1 ? (
          <div className="ic-provider-grid">
            {providers.map((p) => (
              <ProviderCard
                key={p.id}
                provider={p}
                selected={provider?.id === p.id}
                disabled={Boolean(p.coming_soon)}
                onSelect={setProvider}
              />
            ))}
          </div>
        ) : null}

        {step === 2 ? (
          <div className="ic-form">
            <p className="ic-muted">
              OAuth 2.0 is preferred. Secrets are encrypted at rest and never shown again after save.
            </p>
            <label>
              Organization name
              <input value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Acme Corp" />
            </label>
            <label>
              Auth method
              <select value={authMethod} onChange={(e) => setAuthMethod(e.target.value)}>
                <option value="oauth">OAuth 2.0 / Connected App</option>
                <option value="token">Access token</option>
                <option value="password">Username / password</option>
              </select>
            </label>
            {(AUTH_FIELDS[provider.id] || []).map((field) => (
              <label key={field.key}>
                {field.label}
                <input
                  type={field.type || "text"}
                  placeholder={field.placeholder || ""}
                  value={credentials[field.key] || ""}
                  onChange={(e) =>
                    setCredentials((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  autoComplete="off"
                />
              </label>
            ))}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="ic-step-body">
            <div className="ic-step-intro">
              <h3>What should Incentra import?</h3>
              <p>
                Choose the CRM data types to sync. Recommended options are enabled by default for
                commission calculation.
              </p>
            </div>
            <div className="ic-object-grid">
              {[
                {
                  key: "users",
                  title: "People / Owners",
                  desc: "Sales reps and deal owners become employees in Incentra.",
                  example: "Salesforce User · HubSpot Owner",
                  recommended: true,
                },
                {
                  key: "deals",
                  title: "Deals / Opportunities",
                  desc: "Closed-won deals become orders used for commission.",
                  example: "Opportunity · Deal",
                  recommended: true,
                },
                {
                  key: "accounts",
                  title: "Accounts",
                  desc: "Customer accounts for reporting context (optional).",
                  example: "Account · Company",
                  recommended: false,
                },
                {
                  key: "products",
                  title: "Products",
                  desc: "Product catalog lines for product-based plans (optional).",
                  example: "Product2 · Line item",
                  recommended: false,
                },
              ].map((item) => (
                <button
                  key={item.key}
                  type="button"
                  className={`ic-object-card${objects[item.key] ? " is-on" : ""}`}
                  onClick={() =>
                    setObjects((o) => ({ ...o, [item.key]: !o[item.key] }))
                  }
                >
                  <div className="ic-object-card__top">
                    <span className={`ic-switch${objects[item.key] ? " is-on" : ""}`} aria-hidden>
                      <span />
                    </span>
                    {item.recommended ? <em className="ic-rec">Recommended</em> : null}
                  </div>
                  <strong>{item.title}</strong>
                  <p>{item.desc}</p>
                  <span className="ic-object-card__ex">{item.example}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="ic-step-body">
            <div className="ic-step-intro">
              <h3>Match CRM columns to Incentra fields</h3>
              <p>
                For each Incentra field on the right, pick which CRM field provides the value.
                Required fields are marked. Defaults are already filled from {provider?.name || "your CRM"}.
              </p>
              <div className="ic-map-example" aria-hidden>
                <span className="ic-map-example__crm">Email</span>
                <span className="ic-map-example__arrow">→</span>
                <span className="ic-map-example__app">Employee email</span>
              </div>
            </div>

            {(["users", "deals"])
              .filter((obj) => (obj === "users" ? objects.users : objects.deals))
              .map((obj) => (
                <div key={obj} className="ic-map-section">
                  <div className="ic-map-section__head">
                    <h4>{obj === "users" ? "People mapping" : "Deal / opportunity mapping"}</h4>
                    <span className="ic-muted">
                      {obj === "users"
                        ? "Who earns commission"
                        : "What sales count toward commission"}
                    </span>
                  </div>
                  <div className="ic-map-rows">
                    <div className="ic-map-rows__labels">
                      <span>From {provider?.name || "CRM"}</span>
                      <span>Incentra field</span>
                    </div>
                    {(targetFields[obj] || []).map((target) => {
                      const row =
                        mappings.find(
                          (m) => m.source_object === obj && m.target_field === target.field
                        ) || { source_field: "" };
                      const mapped = Boolean(row.source_field);
                      return (
                        <div
                          key={`${obj}-${target.field}`}
                          className={`ic-map-row${mapped ? " is-mapped" : ""}${
                            target.required && !mapped ? " is-missing" : ""
                          }`}
                        >
                          <label className="ic-map-row__source">
                            <span className="ic-sr-only">CRM field for {target.label}</span>
                            <select
                              value={row.source_field || ""}
                              onChange={(e) => {
                                const source_field = e.target.value;
                                setMappings((prev) => {
                                  const next = prev.filter(
                                    (m) =>
                                      !(
                                        m.source_object === obj &&
                                        m.target_field === target.field
                                      )
                                  );
                                  next.push({
                                    source_object: obj,
                                    source_field,
                                    target_field: target.field,
                                    is_required: target.required,
                                  });
                                  return next;
                                });
                              }}
                            >
                              <option value="">Choose CRM field…</option>
                              {(sourceFields[obj] || []).map((sf) => (
                                <option key={sf} value={sf}>
                                  {sf}
                                </option>
                              ))}
                              {obj === "deals" ? (
                                <option value="=Booked">Fixed value: Booked</option>
                              ) : null}
                              {obj === "users" ? (
                                <option value="=Sales Rep">Fixed value: Sales Rep</option>
                              ) : null}
                            </select>
                          </label>
                          <span className="ic-map-row__arrow" aria-hidden>
                            →
                          </span>
                          <div className="ic-map-row__target">
                            <strong>
                              {target.label}
                              {target.required ? (
                                <span className="ic-req"> Required</span>
                              ) : (
                                <span className="ic-opt"> Optional</span>
                              )}
                            </strong>
                            <span>
                              {target.field === "crm_user_id"
                                ? "Links the CRM person to the Incentra employee"
                                : target.field === "crm_owner_id"
                                  ? "Must match a synced person’s CRM ID"
                                  : target.field === "sales_amount"
                                    ? "Deal amount used in commission calc"
                                    : target.field === "order_status"
                                      ? "Usually Booked until finance approves"
                                      : `Stored as ${target.field}`}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}

            {!objects.users && !objects.deals ? (
              <p className="ic-warn">
                Turn on People or Deals in the Objects step to configure mapping.
              </p>
            ) : null}
          </div>
        ) : null}

        {step === 5 ? (
          <div className="ic-form">
            <label className="ic-check">
              <input
                type="checkbox"
                checked={rules.closed_won_only}
                onChange={(e) => setRules((r) => ({ ...r, closed_won_only: e.target.checked }))}
              />
              When opportunity is Closed Won
            </label>
            <label>
              Import status
              <select
                value={rules.import_status}
                onChange={(e) => setRules((r) => ({ ...r, import_status: e.target.value }))}
              >
                <option value="Booked">Booked</option>
                <option value="Success">Success</option>
              </select>
            </label>
            <label className="ic-check">
              <input
                type="checkbox"
                checked={rules.commission_after_approval}
                onChange={(e) =>
                  setRules((r) => ({ ...r, commission_after_approval: e.target.checked }))
                }
              />
              Commission calculation after admin approval
            </label>
            <label>
              Sync frequency
              <select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                <option value="realtime">Real-time</option>
                <option value="hourly">Hourly</option>
                <option value="daily">Daily</option>
                <option value="manual">Manual</option>
              </select>
            </label>
          </div>
        ) : null}

        {step === 6 ? (
          <div>
            <h3>Data preview</h3>
            <p className="ic-muted">
              Review sample records before ongoing sync. Estimated batch:{" "}
              {preview?.estimated_total ?? "—"}
            </p>
            <div className="ic-table-wrap">
              <table className="ic-table">
                <thead>
                  <tr>
                    <th>Opportunity ID</th>
                    <th>Amount</th>
                    <th>Owner</th>
                    <th>Close Date</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(preview?.records || []).length === 0 ? (
                    <tr>
                      <td colSpan={5}>No preview rows (auth or filters may need adjustment).</td>
                    </tr>
                  ) : (
                    (preview.records || []).map((r, idx) => (
                      <tr key={idx}>
                        <td>{r.opportunity_id || r.name || "—"}</td>
                        <td>{r.amount ?? "—"}</td>
                        <td>{r.owner || "—"}</td>
                        <td>{r.close_date || "—"}</td>
                        <td>{r.status || "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        <footer className="ic-modal__foot">
          <button
            type="button"
            className="btn-secondary"
            disabled={step === 1 || busy}
            onClick={() => setStep((s) => Math.max(1, s - 1))}
          >
            Back
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={next}>
            {busy ? "Working…" : step === 6 ? "Finish" : step === 5 ? "Save & preview" : "Continue"}
          </button>
        </footer>
      </div>
    </div>
  );
}

export default function IntegrationCenter() {
  const [tab, setTab] = useState("overview");
  const [summary, setSummary] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [activity, setActivity] = useState(null);
  const [identities, setIdentities] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [validation, setValidation] = useState(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [devOpen, setDevOpen] = useState(false);
  const [configText, setConfigText] = useState("");

  const selected = useMemo(
    () => (summary?.connections || []).find((c) => c.id === selectedId) || null,
    [summary, selectedId]
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, catRes, actRes, idRes] = await Promise.all([
        api.get("integrations/center/summary/"),
        api.get("integrations/center/catalog/"),
        api.get("integrations/center/activity/"),
        api.get("integrations/center/identities/"),
      ]);
      setSummary(sumRes.data);
      setCatalog(catRes.data);
      setActivity(actRes.data);
      setIdentities(idRes.data?.results || []);
      if (!selectedId && sumRes.data.connections?.length) {
        setSelectedId(sumRes.data.connections[0].id);
      }
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Failed to load integration center.");
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId || tab !== "mapping") return;
    api
      .get(`integrations/center/${selectedId}/mappings/`)
      .then((res) => {
        setMappings(res.data.mappings || []);
        setValidation(res.data.validation || null);
      })
      .catch(() => {
        setMappings([]);
      });
    api
      .get(`integrations/${selectedId}/`)
      .then((res) => setConfigText(JSON.stringify(res.data.config || {}, null, 2)))
      .catch(() => setConfigText("{}"));
  }, [selectedId, tab]);

  const runSync = async (id, syncType = "full") => {
    setMessage("");
    try {
      const res = await api.post(`integrations/center/${id}/sync/`, { sync_type: syncType });
      setMessage(
        `Sync finished — processed ${res.data.job?.records_processed ?? 0}, failed ${
          res.data.job?.failed_records ?? 0
        }.`
      );
      await load();
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Sync failed.");
    }
  };

  const disconnect = async (id) => {
    if (!window.confirm("Disconnect this CRM connection?")) return;
    try {
      await api.post(`integrations/center/${id}/disconnect/`);
      setMessage("Connection disconnected.");
      await load();
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Disconnect failed.");
    }
  };

  const saveMappings = async () => {
    if (!selectedId) return;
    try {
      const res = await api.put(`integrations/center/${selectedId}/mappings/`, {
        mappings,
      });
      setMappings(res.data.mappings || []);
      setValidation(res.data.validation || null);
      setMessage("Field mapping updated.");
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Failed to save mappings.");
    }
  };

  const kpis = summary?.kpis || {};

  return (
    <div className="ic-root">
      <header className="ic-header">
        <div>
          <p className="ic-eyebrow">Integrations</p>
          <h1>CRM Integrations</h1>
          <p className="ic-sub">
            Connect Salesforce or HubSpot securely — map fields, preview data, and monitor syncs
            without writing code.
          </p>
        </div>
        <div className="ic-header__actions">
          <button type="button" className="btn-secondary" onClick={load} disabled={loading}>
            Refresh
          </button>
          <button type="button" className="btn-primary" onClick={() => setWizardOpen(true)}>
            Connect CRM
          </button>
        </div>
      </header>

      <section className="ic-kpis">
        <article className="ic-kpi">
          <span>Connected Apps</span>
          <strong>{kpis.connected_apps ?? 0}</strong>
        </article>
        <article className="ic-kpi">
          <span>Last Sync</span>
          <strong>{formatWhen(kpis.last_sync)}</strong>
        </article>
        <article className="ic-kpi">
          <span>Records Imported</span>
          <strong>{kpis.records_imported ?? 0}</strong>
        </article>
        <article className="ic-kpi ic-kpi--warn">
          <span>Sync Errors</span>
          <strong>{kpis.sync_errors ?? 0}</strong>
        </article>
      </section>

      {message ? <p className="ic-banner">{message}</p> : null}

      <div className="ic-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`ic-tabs__btn${tab === t.id ? " is-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" || tab === "connections" ? (
        <section className="ic-grid">
          {(summary?.connections || []).length === 0 ? (
            <div className="panel ic-empty">
              <h2>No CRM systems connected</h2>
              <p>Use the connection wizard to link Salesforce or HubSpot.</p>
              <button type="button" className="btn-primary" onClick={() => setWizardOpen(true)}>
                Connect CRM
              </button>
            </div>
          ) : (
            (summary.connections || []).map((c) => (
              <article key={c.id} className="ic-card panel">
                <div className="ic-card__head">
                  <div>
                    <h3>{c.provider_label}</h3>
                    <p className="ic-muted">{c.name}</p>
                  </div>
                  <span className={`ic-badge ${statusClass(c.status)}`}>{c.status_label}</span>
                </div>
                <dl className="ic-dl">
                  <div>
                    <dt>Last sync</dt>
                    <dd>{formatWhen(c.last_sync)}</dd>
                  </div>
                  <div>
                    <dt>Users</dt>
                    <dd>{c.records?.users ?? 0}</dd>
                  </div>
                  <div>
                    <dt>Deals / Orders</dt>
                    <dd>{c.records?.orders ?? 0}</dd>
                  </div>
                  <div>
                    <dt>Frequency</dt>
                    <dd className="ic-cap">{c.sync_frequency}</dd>
                  </div>
                  <div>
                    <dt>Connected user</dt>
                    <dd>{c.connected_user_email || "—"}</dd>
                  </div>
                </dl>
                <div className="ic-card__actions">
                  <button type="button" className="btn-secondary" onClick={() => { setSelectedId(c.id); setTab("mapping"); }}>
                    View
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => runSync(c.id, "full")}>
                    Sync Now
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => { setSelectedId(c.id); setTab("mapping"); }}>
                    Edit
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => disconnect(c.id)}>
                    Disconnect
                  </button>
                </div>
              </article>
            ))
          )}
        </section>
      ) : null}

      {tab === "mapping" ? (
        <section className="panel ic-panel">
          <div className="ic-panel__head">
            <h2>Field mapping</h2>
            <select
              value={selectedId || ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
            >
              {(summary?.connections || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.provider_label} — {c.name}
                </option>
              ))}
            </select>
          </div>
          {!selected ? (
            <p className="ic-muted">Select a connection.</p>
          ) : (
            <>
              {validation && !validation.ok ? (
                <div className="ic-warn">
                  {(validation.errors || []).map((e, i) => (
                    <div key={i}>{e.message}</div>
                  ))}
                </div>
              ) : null}
              <table className="ic-table">
                <thead>
                  <tr>
                    <th>Object</th>
                    <th>CRM field</th>
                    <th></th>
                    <th>Incentra field</th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map((m, idx) => (
                    <tr key={`${m.source_object}-${m.target_field}-${idx}`}>
                      <td className="ic-cap">{m.source_object}</td>
                      <td>
                        <input
                          value={m.source_field}
                          onChange={(e) => {
                            const v = e.target.value;
                            setMappings((prev) =>
                              prev.map((row, i) => (i === idx ? { ...row, source_field: v } : row))
                            );
                          }}
                        />
                      </td>
                      <td className="ic-arrow">→</td>
                      <td>
                        {m.target_field}
                        {m.is_required ? " *" : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="ic-panel__actions">
                <button type="button" className="btn-primary" onClick={saveMappings}>
                  Save mapping
                </button>
              </div>

              <details className="ic-dev" open={devOpen} onToggle={(e) => setDevOpen(e.target.open)}>
                <summary>Developer settings (JSON config)</summary>
                <p className="ic-muted">Advanced only — normal admins should use the mapping grid above.</p>
                <textarea value={configText} readOnly rows={12} />
              </details>

              <h3>CRM identity mapping</h3>
              <p className="ic-muted">
                Opportunity OwnerId / HubSpot Owner ID must resolve to an Incentra employee.
              </p>
              <table className="ic-table">
                <thead>
                  <tr>
                    <th>CRM provider</th>
                    <th>CRM user ID</th>
                    <th>Incentra employee ID</th>
                    <th>Email</th>
                  </tr>
                </thead>
                <tbody>
                  {identities
                    .filter((i) => !selectedId || i.connection_id === selectedId || !i.connection_id)
                    .slice(0, 50)
                    .map((i) => (
                      <tr key={i.id}>
                        <td>{i.crm_provider}</td>
                        <td>{i.crm_user_id}</td>
                        <td>{i.employee_id}</td>
                        <td>{i.employee_email}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      ) : null}

      {tab === "history" ? (
        <section className="panel ic-panel">
          <h2>Integration activity</h2>
          <table className="ic-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Connection</th>
                <th>Type</th>
                <th>Status</th>
                <th>Processed</th>
                <th>Failed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {[...(activity?.jobs || []), ...(activity?.logs || [])].slice(0, 40).map((job) => (
                <tr key={job.id}>
                  <td>{formatWhen(job.started_at || job.completed_at)}</td>
                  <td>{job.connection_name}</td>
                  <td className="ic-cap">{job.sync_type}</td>
                  <td>
                    <span className={`ic-badge ${statusClass(job.status)}`}>{job.status}</span>
                  </td>
                  <td>{job.records_processed}</td>
                  <td>{job.failed_records}</td>
                  <td>
                    {job.failed_records > 0 && typeof job.id === "number" ? (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          try {
                            await api.post(`integrations/center/jobs/${job.id}/retry/`);
                            setMessage("Retry started.");
                            await load();
                          } catch (err) {
                            setMessage(getApiErrorMessage(err) || "Retry failed.");
                          }
                        }}
                      >
                        Retry failed
                      </button>
                    ) : job.error_details?.length ? (
                      <details>
                        <summary>View errors</summary>
                        <pre className="ic-pre">{JSON.stringify(job.error_details, null, 2)}</pre>
                      </details>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {tab === "logs" ? (
        <section className="panel ic-panel">
          <h2>Audit log</h2>
          <ul className="ic-timeline">
            {(activity?.audit || []).length === 0 ? (
              <li className="ic-muted">No integration audit events yet.</li>
            ) : (
              (activity.audit || []).map((row) => (
                <li key={row.id}>
                  <strong>{row.message}</strong>
                  <span className="ic-muted">{formatWhen(row.created_at)}</span>
                </li>
              ))
            )}
          </ul>
          <p className="ic-muted">
            Full org audit trail also available in <Link to="/audit-logs">Audit Log</Link>.
          </p>
        </section>
      ) : null}

      {wizardOpen ? (
        <ConnectionWizard
          catalog={catalog}
          onClose={() => setWizardOpen(false)}
          onCreated={load}
        />
      ) : null}
    </div>
  );
}
