import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import PageChrome, { ChromeButton } from "../Components/layout/PageChrome";
import { useToast } from "../Components/Toast";
import {
  UploadWizard,
  approvalBadge,
  fetchDocumentBlob,
  formatDate,
  formatDateTime,
  formatMonthYear,
  periodLabel,
  statusBadge,
} from "./documentsShared";
import "./documents.css";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "preview", label: "Preview" },
  { id: "versions", label: "Versions" },
  { id: "approvals", label: "Approvals" },
  { id: "links", label: "Linked Plans" },
  { id: "audit", label: "Audit History" },
];

function DocumentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");
  const [previewUrl, setPreviewUrl] = useState(null);
  const [downloadReason, setDownloadReason] = useState("");
  const [versionOpen, setVersionOpen] = useState(false);
  const [profile, setProfile] = useState(null);
  const [plans, setPlans] = useState([]);
  const [people, setPeople] = useState([]);
  const [rules, setRules] = useState([]);

  const canManage = Boolean(profile?.is_admin || profile?.is_finance);
  const canDelete = Boolean(profile?.is_admin);
  const rel = doc?.relationships || {};
  const versions = doc?.versions || [];
  const isPdf =
    (doc?.content_type || "").includes("pdf") || (doc?.file_name || "").toLowerCase().endsWith(".pdf");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dRes, me, pRes, peopleRes, rRes] = await Promise.all([
        api.get(`documents/${id}/`),
        api.get("user-profile/").catch(() => ({ data: null })),
        api.get("compensation-plans/").catch(() => ({ data: [] })),
        api.get("user-setup/").catch(() => ({ data: [] })),
        api.get("commission-rules/").catch(() => ({ data: [] })),
      ]);
      setDoc(dRes.data);
      setProfile(me.data);
      setPlans(Array.isArray(pRes.data) ? pRes.data : pRes.data?.results || []);
      const plist = Array.isArray(peopleRes.data) ? peopleRes.data : peopleRes.data?.results || [];
      setPeople(
        plist.filter((p) => {
          const role = String(p.role || "").toLowerCase();
          return role.includes("admin") || role.includes("finance") || role.includes("manager");
        })
      );
      setRules(Array.isArray(rRes.data) ? rRes.data : rRes.data?.results || []);
    } catch (err) {
      error({ title: "Unable to load document", message: getApiErrorMessage(err) });
      navigate("/documents");
    } finally {
      setLoading(false);
    }
  }, [id, error, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    let revoked = false;
    let url;
    (async () => {
      if (!doc?.id || !doc.current_version?.has_file || tab !== "preview") {
        setPreviewUrl(null);
        return;
      }
      try {
        const blob = await fetchDocumentBlob(doc.id, {
          inline: true,
          reason: "Document preview in governance center",
        });
        url = URL.createObjectURL(blob);
        if (!revoked) setPreviewUrl(url);
      } catch {
        if (!revoked) setPreviewUrl(null);
      }
    })();
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [doc?.id, doc?.current_version?.id, doc?.current_version?.has_file, tab]);

  const download = async (versionId) => {
    try {
      const blob = await fetchDocumentBlob(doc.id, {
        versionId,
        reason: downloadReason || "Compliance evidence download",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.current_version?.file_name || `${doc.name}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      error({ title: "Download failed", message: err.message || "Try again." });
    }
  };

  const runAction = async (fn, okTitle, okMsg) => {
    try {
      await fn();
      success({ title: okTitle, message: okMsg });
      load();
    } catch (err) {
      error({ title: "Action failed", message: getApiErrorMessage(err) });
    }
  };

  if (loading || !doc) {
    return (
      <div className="cdr-root">
        <p className="cdr-muted" style={{ padding: 24 }}>
          Loading compliance record…
        </p>
      </div>
    );
  }

  return (
    <div className="cdr-root">
      <PageChrome
        eyebrow="Compensation compliance"
        title={doc.name}
        subtitle={`Prove plan, approval, version, and calculation evidence · ${doc.document_type_label}`}
        primaryAction={
          <div className="cdr-detail-actions">
            <ChromeButton onClick={() => navigate("/documents")}>Back to center</ChromeButton>
            {canManage ? (
              <ChromeButton variant="primary" onClick={() => setVersionOpen(true)}>
                New version
              </ChromeButton>
            ) : null}
          </div>
        }
      >
        <div className="cdr-detail-strip">
          {statusBadge(doc.status)}
          {approvalBadge(doc.approval_status)}
          <span className="cdr-pill">Version {doc.version || "—"}</span>
          <span className="cdr-pill">Effective {periodLabel(doc)}</span>
          <span className="cdr-pill">Owner {doc.owner || "—"}</span>
        </div>

        <nav className="cdr-tabs" aria-label="Document sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? "is-active" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="cdr-tab-panel">
          {tab === "overview" ? (
            <div className="cdr-overview-grid">
              <section className="cdr-panel">
                <h3>Document record</h3>
                <dl className="cdr-kv">
                  <div>
                    <dt>Name</dt>
                    <dd>{doc.name}</dd>
                  </div>
                  <div>
                    <dt>Category</dt>
                    <dd>{doc.category || doc.document_type_label}</dd>
                  </div>
                  <div>
                    <dt>Linked compensation plan</dt>
                    <dd>
                      {doc.related_plan_id ? (
                        <Link to={`/comp-plans/${doc.related_plan_id}/documents`}>
                          {doc.related_plan_name}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Linked commission rules</dt>
                    <dd>{doc.linked_rule_names || "—"}</dd>
                  </div>
                  <div>
                    <dt>Version</dt>
                    <dd>{doc.version || "—"}</dd>
                  </div>
                  <div>
                    <dt>Effective period</dt>
                    <dd>{periodLabel(doc)}</dd>
                  </div>
                  <div>
                    <dt>Owner</dt>
                    <dd>{doc.owner || "—"}</dd>
                  </div>
                  <div>
                    <dt>Approval status</dt>
                    <dd>{approvalBadge(doc.approval_status)}</dd>
                  </div>
                  <div>
                    <dt>Last activity</dt>
                    <dd>{formatDateTime(doc.last_activity_at)}</dd>
                  </div>
                </dl>
              </section>
              <section className="cdr-panel">
                <h3>Evidence chain</h3>
                <p className="cdr-muted">
                  This record supports commission calculations by proving which plan and version were
                  approved and active.
                </p>
                <ul className="cdr-evidence">
                  <li>
                    <strong>Plan used</strong>
                    <span>{doc.related_plan_name || "Not linked"}</span>
                  </li>
                  <li>
                    <strong>Approved by</strong>
                    <span>
                      {doc.approved_by || "Pending"}
                      {doc.approved_at ? ` · ${formatDate(doc.approved_at)}` : ""}
                    </span>
                  </li>
                  <li>
                    <strong>Active version</strong>
                    <span>{doc.version || "—"}</span>
                  </li>
                  <li>
                    <strong>Calculations referencing this document</strong>
                    <span>{rel.calculation_count ?? 0}</span>
                  </li>
                </ul>
                <div className="cdr-drawer__actions" style={{ marginTop: 16 }}>
                  <ChromeButton onClick={() => download()}>Download evidence</ChromeButton>
                  {canManage && doc.status === "pending_review" ? (
                    <>
                      <ChromeButton
                        onClick={() =>
                          runAction(
                            () => api.post(`documents/${doc.id}/review/`, { reason: "Reviewed" }),
                            "Reviewed",
                            "Marked as reviewed."
                          )
                        }
                      >
                        Mark reviewed
                      </ChromeButton>
                      <ChromeButton
                        onClick={() =>
                          runAction(
                            () =>
                              api.post(`documents/${doc.id}/approve/`, {
                                reason: "Approved in governance center",
                                publish: true,
                              }),
                            "Approved",
                            "Document approved and published when eligible."
                          )
                        }
                      >
                        Approve & publish
                      </ChromeButton>
                    </>
                  ) : null}
                  {canManage && doc.status === "approved" ? (
                    <ChromeButton
                      onClick={() =>
                        runAction(
                          () => api.post(`documents/${doc.id}/publish/`, { reason: "Published" }),
                          "Published",
                          "Document is now published for calculations."
                        )
                      }
                    >
                      Publish
                    </ChromeButton>
                  ) : null}
                  {canManage && doc.status !== "archived" ? (
                    <ChromeButton
                      onClick={() =>
                        runAction(
                          () => api.patch(`documents/${doc.id}/`, { status: "archived" }),
                          "Archived",
                          "Document archived."
                        )
                      }
                    >
                      Archive
                    </ChromeButton>
                  ) : null}
                  {canDelete ? (
                    <ChromeButton
                      onClick={async () => {
                        if (!window.confirm(`Delete “${doc.name}”?`)) return;
                        await runAction(
                          () => api.delete(`documents/${doc.id}/`),
                          "Deleted",
                          "Document removed."
                        );
                        navigate("/documents");
                      }}
                    >
                      Delete
                    </ChromeButton>
                  ) : null}
                </div>
                <label style={{ display: "block", marginTop: 12 }}>
                  <span className="cdr-muted">Download reason (audit)</span>
                  <input
                    className="cdr-reason"
                    value={downloadReason}
                    onChange={(e) => setDownloadReason(e.target.value)}
                    placeholder="e.g. Commission dispute review"
                  />
                </label>
              </section>
            </div>
          ) : null}

          {tab === "preview" ? (
            <section className="cdr-panel cdr-preview-panel">
              {previewUrl && isPdf ? (
                <iframe title="Document preview" src={previewUrl} className="cdr-preview-frame" />
              ) : (
                <div className="cdr-preview-empty">
                  <strong>{doc.file_name || "No file attached"}</strong>
                  <p>
                    {doc.current_version?.has_file
                      ? "Preview available for PDF. Download for other formats."
                      : "Upload a version to enable preview."}
                  </p>
                  {doc.current_version?.has_file ? (
                    <ChromeButton onClick={() => download()}>Download</ChromeButton>
                  ) : null}
                </div>
              )}
            </section>
          ) : null}

          {tab === "versions" ? (
            <section className="cdr-panel">
              <div className="cdr-section-head">
                <div>
                  <h3>Version history</h3>
                  <p className="cdr-muted">Current version {doc.version || "—"} · never overwrite files</p>
                </div>
                {canManage ? (
                  <ChromeButton onClick={() => setVersionOpen(true)}>Upload new version</ChromeButton>
                ) : null}
              </div>
              <ol className="cdr-versions cdr-versions--wide">
                {versions.map((v) => (
                  <li key={v.id} className={v.id === doc.current_version?.id ? "is-active" : ""}>
                    <div>
                      <strong>{v.version_label}</strong>
                      {statusBadge(v.status)}
                      {approvalBadge(v.approval_status)}
                    </div>
                    <p>
                      {formatMonthYear(v.effective_from) || "…"} – {formatMonthYear(v.effective_to) || "…"}
                      {" · "}
                      Uploaded {formatDate(v.created_at)} by {v.uploaded_by || "—"}
                    </p>
                    <div className="cdr-version-actions">
                      <button type="button" className="cdr-link" onClick={() => download(v.id)}>
                        Download
                      </button>
                      {canManage && v.id !== doc.current_version?.id ? (
                        <button
                          type="button"
                          className="cdr-link"
                          onClick={() =>
                            runAction(
                              () =>
                                api.post(`documents/${doc.id}/versions/${v.id}/restore/`, {
                                  reason: `Restored ${v.version_label}`,
                                }),
                              "Restored",
                              `${v.version_label} is now current.`
                            )
                          }
                        >
                          Restore
                        </button>
                      ) : null}
                      <span className="cdr-muted">Compare (soon)</span>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          {tab === "approvals" ? (
            <section className="cdr-panel">
              <h3>Approval workflow</h3>
              <div className="cdr-approval-track">
                {[
                  ["Created by", doc.created_by, doc.created_at],
                  ["Reviewed by", doc.reviewed_by, doc.reviewed_at],
                  ["Approved by", doc.approved_by, doc.approved_at],
                ].map(([label, who, when]) => (
                  <article key={label}>
                    <span>{label}</span>
                    <strong>{who || "—"}</strong>
                    <em>{when ? formatDateTime(when) : "Pending"}</em>
                  </article>
                ))}
              </div>
              <dl className="cdr-kv" style={{ marginTop: 16 }}>
                <div>
                  <dt>Approval status</dt>
                  <dd>{approvalBadge(doc.approval_status)}</dd>
                </div>
                <div>
                  <dt>Lifecycle</dt>
                  <dd>{statusBadge(doc.status)}</dd>
                </div>
                <div>
                  <dt>Approval date</dt>
                  <dd>{doc.approved_at ? formatDateTime(doc.approved_at) : "—"}</dd>
                </div>
              </dl>
            </section>
          ) : null}

          {tab === "links" ? (
            <div className="cdr-overview-grid">
              <section className="cdr-panel">
                <h3>Compensation plans</h3>
                {(rel.linked_plans || []).length ? (
                  <ul className="cdr-link-list">
                    {rel.linked_plans.map((p) => (
                      <li key={p.id}>
                        <Link to={`/comp-plans/${p.id}/documents`}>{p.name}</Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="cdr-muted">No plan linked.</p>
                )}
                <h3 style={{ marginTop: 20 }}>Commission rules</h3>
                {(rel.linked_rules || []).length ? (
                  <ul className="cdr-link-list">
                    {rel.linked_rules.map((r) => (
                      <li key={r.id}>
                        <strong>{r.name}</strong>
                        <span className="cdr-muted">
                          {" "}
                          · {r.rule_type}
                          {r.is_active ? "" : " (inactive)"}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="cdr-muted">No rules linked.</p>
                )}
              </section>
              <section className="cdr-panel">
                <h3>Commission calculations</h3>
                <p className="cdr-muted">
                  Calculations that reference this document as supporting evidence.
                </p>
                {(rel.commission_calculations || []).length ? (
                  <table className="cdr-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Employee</th>
                        <th>Amount</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rel.commission_calculations.map((c) => (
                        <tr key={c.id}>
                          <td>{c.id}</td>
                          <td>{c.employee || "—"}</td>
                          <td>{c.amount || "—"}</td>
                          <td>{c.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="cdr-muted">No calculations linked yet.</p>
                )}
              </section>
            </div>
          ) : null}

          {tab === "audit" ? (
            <section className="cdr-panel">
              <h3>Audit history</h3>
              <ul className="cdr-audit-list">
                {(rel.audit_history || []).length ? (
                  rel.audit_history.map((a) => (
                    <li key={a.id}>
                      <time>{formatDateTime(a.timestamp)}</time>
                      <strong>
                        {(a.user_email || "User").split("@")[0]} · {a.action_label}
                      </strong>
                      {a.reason ? <em>{a.reason}</em> : null}
                    </li>
                  ))
                ) : (
                  <li className="cdr-muted">No audit events yet.</li>
                )}
              </ul>
            </section>
          ) : null}
        </div>
      </PageChrome>

      <UploadWizard
        open={versionOpen}
        initial={doc}
        plans={plans}
        people={people}
        rules={rules}
        onClose={() => setVersionOpen(false)}
        onSaved={load}
      />
    </div>
  );
}

export default DocumentDetail;
