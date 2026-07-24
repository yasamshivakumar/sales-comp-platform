import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import PageChrome, { ChromeButton } from "../Components/layout/PageChrome";
import { useToast } from "../Components/Toast";
import {
  CATEGORY_META,
  DOC_TYPES,
  LIFECYCLE,
  UploadWizard,
  approvalBadge,
  formatDateTime,
  periodLabel,
  statusBadge,
} from "./documentsShared";
import "./documents.css";

function DocumentLibrary() {
  const navigate = useNavigate();
  const { error } = useToast();
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [plans, setPlans] = useState([]);
  const [people, setPeople] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [templateMode, setTemplateMode] = useState(false);
  const [versionFor, setVersionFor] = useState(null);
  const [filters, setFilters] = useState({
    q: "",
    document_type: "",
    status: "",
    related_plan: "",
  });

  const canUpload = Boolean(profile?.is_admin || profile?.is_finance);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      const qs = params.toString() ? `?${params}` : "";
      const [sRes, dRes, pRes, me, peopleRes, rRes] = await Promise.all([
        api.get("documents/summary/"),
        api.get(`documents/${qs}`),
        api.get("compensation-plans/").catch(() => ({ data: [] })),
        api.get("user-profile/").catch(() => ({ data: null })),
        api.get("user-setup/").catch(() => ({ data: [] })),
        api.get("commission-rules/").catch(() => ({ data: [] })),
      ]);
      setSummary(sRes.data);
      setRows(dRes.data?.results || []);
      setPlans(Array.isArray(pRes.data) ? pRes.data : pRes.data?.results || []);
      setProfile(me.data);
      const plist = Array.isArray(peopleRes.data) ? peopleRes.data : peopleRes.data?.results || [];
      setPeople(
        plist.filter((p) => {
          const role = String(p.role || "").toLowerCase();
          return role.includes("admin") || role.includes("finance") || role.includes("manager");
        })
      );
      setRules(Array.isArray(rRes.data) ? rRes.data : rRes.data?.results || []);
    } catch (err) {
      error({ title: "Unable to load governance center", message: getApiErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }, [filters, error]);

  useEffect(() => {
    load();
  }, [load]);

  const categoryCounts = useMemo(() => {
    const map = {};
    (summary?.categories || []).forEach((c) => {
      map[c.key] = c.count;
    });
    return map;
  }, [summary]);

  const score = summary?.governance_score ?? 0;
  const scoreTone = score >= 80 ? "good" : score >= 55 ? "warn" : "bad";

  return (
    <div className="cdr-root">
      <PageChrome
        eyebrow="Compensation compliance"
        title="Compensation Governance Center"
        subtitle="Prove which plan was used, who approved it, which version was active, and what document supports each commission calculation."
        primaryAction={
          canUpload ? (
            <ChromeButton
              variant="primary"
              onClick={() => {
                setTemplateMode(false);
                setUploadOpen(true);
              }}
            >
              + Register Document
            </ChromeButton>
          ) : null
        }
        search={
          <input
            value={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
            placeholder="Search governance documents"
            aria-label="Search documents"
          />
        }
        filters={
          <>
            <select
              value={filters.document_type}
              onChange={(e) => setFilters((f) => ({ ...f, document_type: e.target.value }))}
            >
              <option value="">All categories</option>
              {DOC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <select
              value={filters.related_plan}
              onChange={(e) => setFilters((f) => ({ ...f, related_plan: e.target.value }))}
            >
              <option value="">All plans</option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.plan_name}
                </option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            >
              {LIFECYCLE.map((s) => (
                <option key={s.value || "all"} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </>
        }
      >
        {(summary?.alerts || []).length ? (
          <section className="cdr-alerts" aria-label="Compliance alerts">
            {summary.alerts.map((a) => (
              <article key={a.code} className={`cdr-alert severity-${a.severity || "warning"}`}>
                <strong>Compliance alert</strong>
                <span>{a.message}</span>
              </article>
            ))}
          </section>
        ) : null}

        <section className="cdr-health" aria-label="Governance health">
          <article className={`cdr-score cdr-score--${scoreTone}`}>
            <span>Governance Score</span>
            <strong>{score}%</strong>
            <p>Compliance posture across approvals, renewals, and evidence coverage.</p>
          </article>
          {[
            ["Approved Documents", summary?.approved_documents, "Approved or published evidence"],
            ["Pending Approvals", summary?.pending_approval, "Waiting for review / approval"],
            ["Expiring Documents", summary?.expiring, "Renewal needed within 30 days"],
            ["Missing Evidence", summary?.missing_evidence, "Plans without approved documents"],
          ].map(([label, value, hint]) => (
            <article key={label} className="cdr-kpi">
              <span>{label}</span>
              <strong>{value ?? "—"}</strong>
              <p>{hint}</p>
            </article>
          ))}
        </section>

        <section className="cdr-categories" aria-label="Document categories">
          {CATEGORY_META.map((c) => (
            <button
              key={c.key}
              type="button"
              className={`cdr-cat ${filters.document_type === c.key ? "is-active" : ""}`}
              onClick={() =>
                setFilters((f) => ({
                  ...f,
                  document_type: f.document_type === c.key ? "" : c.key,
                }))
              }
            >
              <span>{c.label}</span>
              <strong>{categoryCounts[c.key] ?? 0}</strong>
              <em>{c.hint}</em>
            </button>
          ))}
        </section>

        <div className="cdr-main-grid">
          <div className="cdr-table-wrap">
            {loading ? (
              <p className="cdr-muted" style={{ padding: 24 }}>
                Loading compliance repository…
              </p>
            ) : !rows.length ? (
              <div className="cdr-empty cdr-empty--hero">
                <p className="cdr-eyebrow">Audit-ready onboarding</p>
                <strong>Build your compensation audit trail</strong>
                <p>
                  Upload compensation plans, commission policies, approval records, and employee
                  agreements. Incentra keeps every version linked with compensation calculations and
                  audit history.
                </p>
                {canUpload ? (
                  <div className="cdr-empty__actions">
                    <button
                      type="button"
                      className="pg-btn pg-btn--primary"
                      onClick={() => {
                        setTemplateMode(false);
                        setUploadOpen(true);
                      }}
                    >
                      Upload First Document
                    </button>
                    <ChromeButton
                      onClick={() => {
                        setTemplateMode(true);
                        setUploadOpen(true);
                      }}
                    >
                      Create Document Template
                    </ChromeButton>
                  </div>
                ) : null}
              </div>
            ) : (
              <table className="cdr-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Linked Plan</th>
                    <th>Rules</th>
                    <th>Version</th>
                    <th>Effective</th>
                    <th>Owner</th>
                    <th>Approval</th>
                    <th>Lifecycle</th>
                    <th>Last Activity</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <Link className="cdr-name" to={`/documents/${r.id}`}>
                          {r.name}
                        </Link>
                        {r.business_unit ? <span className="cdr-sub">{r.business_unit}</span> : null}
                      </td>
                      <td>{r.category || r.document_type_label}</td>
                      <td>{r.related_plan_name || "—"}</td>
                      <td>{r.linked_rule_names || "—"}</td>
                      <td>{r.version || "—"}</td>
                      <td>{periodLabel(r)}</td>
                      <td>{r.owner || r.uploaded_by || "—"}</td>
                      <td>{approvalBadge(r.approval_status)}</td>
                      <td>{statusBadge(r.status)}</td>
                      <td>{formatDateTime(r.last_activity_at)}</td>
                      <td className="cdr-actions">
                        <button type="button" onClick={() => navigate(`/documents/${r.id}`)}>
                          Open
                        </button>
                        {canUpload ? (
                          <button type="button" onClick={() => setVersionFor(r)}>
                            Version
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <aside className="cdr-activity" aria-label="Document activity">
            <header>
              <h3>Document Activity</h3>
              <p>Uploads, approvals, downloads, and restores.</p>
            </header>
            <ul>
              {(summary?.recent_activity || []).length ? (
                summary.recent_activity.map((a) => (
                  <li key={a.id}>
                    <time>{formatDateTime(a.timestamp)}</time>
                    <strong>
                      {(a.user_email || "User").split("@")[0]} {a.action_label?.toLowerCase() || a.action}
                    </strong>
                    <span>{a.document_name || a.detail?.file || "—"}</span>
                    {a.reason ? <em>{a.reason}</em> : null}
                  </li>
                ))
              ) : (
                <li className="cdr-activity__empty">
                  <strong>No activity yet</strong>
                  <span>Compliance events will appear here.</span>
                </li>
              )}
            </ul>
          </aside>
        </div>
      </PageChrome>

      <UploadWizard
        open={uploadOpen || Boolean(versionFor)}
        initial={versionFor}
        asTemplate={templateMode && !versionFor}
        plans={plans}
        people={people}
        rules={rules}
        onClose={() => {
          setUploadOpen(false);
          setVersionFor(null);
          setTemplateMode(false);
        }}
        onSaved={load}
      />
    </div>
  );
}

export default DocumentLibrary;
