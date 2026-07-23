import { NavLink, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import LoadingCenter from "../Components/LoadingCenter";
import { StatusBadge } from "./PeopleDataGrid";

const TABS = [
  { to: "overview", label: "Overview" },
  { to: "organization", label: "Organization" },
  { to: "compensation", label: "Compensation" },
  { to: "quota", label: "Quota & Attainment" },
  { to: "commissions", label: "Commission History" },
  { to: "transactions", label: "Transactions" },
  { to: "access", label: "Access" },
  { to: "audit", label: "Audit Log" },
];

const LIFECYCLE_STEPS = [
  "Invited",
  "Pending Activation",
  "Active",
  "Plan Assigned",
  "Suspended",
  "Inactive",
];

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

function formatDateShort(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString();
}

function OverviewTab({ person, onResend, onRevoke, onCopyLink, busy }) {
  const inv = person.invitation || {};
  return (
    <div className="pe-tab">
      <h2>Overview</h2>
      <dl className="pe-overview-grid">
        <div>
          <dt>Employee Name</dt>
          <dd>{person.display_name || person.name}</dd>
        </div>
        <div>
          <dt>Employee ID</dt>
          <dd>{person.employee_id || "—"}</dd>
        </div>
        <div>
          <dt>Position</dt>
          <dd>{person.position || person.position_name || "—"}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{person.role || "—"}</dd>
        </div>
        <div>
          <dt>Territory</dt>
          <dd>{person.territory_name || "—"}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            <StatusBadge code={person.status} label={person.status_label} />
          </dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{person.email}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>{person.phone || "—"}</dd>
        </div>
        <div>
          <dt>Joining Date</dt>
          <dd>{formatDateShort(person.hire_date)}</dd>
        </div>
        <div>
          <dt>Last Login</dt>
          <dd>{formatDate(person.last_login)}</dd>
        </div>
      </dl>

      <div className="pe-invite-box">
        <h3>Participant lifecycle</h3>
        <ol className="pe-lifecycle">
          {LIFECYCLE_STEPS.map((step) => (
            <li
              key={step}
              className={
                person.status_label === step || inv.label === step ? "is-active" : ""
              }
            >
              {step}
            </li>
          ))}
        </ol>
        <p>
          <strong>{inv.label || person.status_label}</strong>
          {inv.expires_at ? <> · Expires {formatDate(inv.expires_at)}</> : null}
        </p>
        <div className="pe-tab__actions">
          {inv.can_resend || person.enable_login ? (
            <button type="button" className="btn-primary" disabled={busy} onClick={onResend}>
              Resend Invite
            </button>
          ) : null}
          {inv.can_copy_link || person.enable_login ? (
            <button type="button" className="btn-secondary" disabled={busy} onClick={onCopyLink}>
              Copy Invite Link
            </button>
          ) : null}
          {inv.can_revoke ? (
            <button type="button" className="btn-secondary" disabled={busy} onClick={onRevoke}>
              Revoke Invite
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function OrganizationTab({ person }) {
  const chain = person.hierarchy_chain || [];
  return (
    <div className="pe-tab">
      <h2>Organization</h2>
      <dl className="pe-overview-grid">
        <div>
          <dt>Manager</dt>
          <dd>{person.manager_name || "—"}</dd>
        </div>
        <div>
          <dt>Direct Reports</dt>
          <dd>{person.direct_report_count ?? 0}</dd>
        </div>
        <div>
          <dt>Department</dt>
          <dd>{person.department || "—"}</dd>
        </div>
        <div>
          <dt>Business Unit</dt>
          <dd>{person.business_unit || person.business_group || "—"}</dd>
        </div>
        <div>
          <dt>Position</dt>
          <dd>{person.position || "—"}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{person.region || "—"}</dd>
        </div>
        <div>
          <dt>Territory</dt>
          <dd>{person.territory_name || "—"}</dd>
        </div>
      </dl>

      <h3>Organization tree</h3>
      {chain.length === 0 ? (
        <p className="pe-muted">No reporting chain configured.</p>
      ) : (
        <ol className="pe-hierarchy">
          {chain.map((node, idx) => (
            <li key={node.id} className={node.is_self ? "is-self" : ""}>
              <strong>{node.name}</strong>
              <span>
                {node.role}
                {node.employee_id ? ` · ${node.employee_id}` : ""}
              </span>
              {idx < chain.length - 1 ? <span className="pe-hierarchy__arrow">↓</span> : null}
            </li>
          ))}
        </ol>
      )}

      {(person.direct_reports || []).length > 0 ? (
        <>
          <h3>Direct reports</h3>
          <ul className="pe-report-list">
            {person.direct_reports.map((r) => (
              <li key={r.id}>
                <strong>{r.name}</strong>
                <span>
                  {r.employee_id} · {r.role}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

function CompensationTab({ person, onSave, busy }) {
  const pc = person.participant_compensation || {};
  const [eligible, setEligible] = useState(Boolean(pc.commission_eligible ?? person.commission_eligible));
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(
    String(person.assigned_plan_id || pc.assigned_plan?.id || "")
  );

  useEffect(() => {
    setEligible(Boolean(pc.commission_eligible ?? person.commission_eligible));
    setPlanId(String(person.assigned_plan_id || pc.assigned_plan?.id || ""));
  }, [person, pc]);

  useEffect(() => {
    api
      .get("compensation-plans/", { params: { page_size: 100, status: "Active" } })
      .then((res) => {
        const data = res.data;
        setPlans(Array.isArray(data) ? data : data?.results || []);
      })
      .catch(() => setPlans([]));
  }, []);

  return (
    <div className="pe-tab">
      <h2>Compensation</h2>
      <div className="pe-participant-card">
        <div>
          <span className="pe-expand__label">Current Plan</span>
          <strong>{pc.assigned_plan_name || person.assigned_plan_name || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Calculation Method</span>
          <strong>{pc.calculation_method || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Quota</span>
          <strong>{pc.quota_display || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Effective Period</span>
          <strong>{pc.effective_period || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Eligibility</span>
          <strong className={eligible ? "pe-yes" : "pe-no"}>{eligible ? "YES" : "NO"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Commission Role</span>
          <strong>{pc.commission_role || person.role || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Territory</span>
          <strong>{pc.territory_name || person.territory_name || "—"}</strong>
        </div>
      </div>
      <label className="form-field">
        Assign compensation plan
        <select value={planId} onChange={(e) => setPlanId(e.target.value)}>
          <option value="">— Unassigned —</option>
          {plans.map((p) => (
            <option key={p.id} value={p.id}>
              {p.plan_name}
            </option>
          ))}
        </select>
      </label>
      <label className="checkbox-field">
        <input type="checkbox" checked={eligible} onChange={(e) => setEligible(e.target.checked)} />
        Commission eligible
      </label>
      <button
        type="button"
        className="btn-primary"
        disabled={busy}
        onClick={() =>
          onSave({
            commission_eligible: eligible,
            assigned_plan_id: planId || null,
          })
        }
      >
        Save compensation
      </button>
    </div>
  );
}

function QuotaTab({ person, onSave, busy }) {
  const qa = person.quota_attainment || {};
  const [quota, setQuota] = useState(String(person.personal_target ?? qa.quota ?? ""));
  const [effective, setEffective] = useState(qa.effective_date || person.comp_effective_date || "");

  useEffect(() => {
    setQuota(String(person.personal_target ?? qa.quota ?? ""));
    setEffective(qa.effective_date || person.comp_effective_date || "");
  }, [person, qa]);

  return (
    <div className="pe-tab">
      <h2>Quota & Attainment</h2>
      <div className="pe-participant-card">
        <div>
          <span className="pe-expand__label">Quota</span>
          <strong>{qa.quota_display || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Credited Sales</span>
          <strong>{qa.credited_sales_display || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Remaining</span>
          <strong>{qa.remaining_display || "—"}</strong>
        </div>
        <div>
          <span className="pe-expand__label">Attainment</span>
          <strong>
            {qa.attainment_pct != null ? `${qa.attainment_pct}%` : "—"}
          </strong>
        </div>
      </div>
      {qa.attainment_pct != null ? (
        <div className="pe-attainment-bar" aria-hidden>
          <div
            className="pe-attainment-bar__fill"
            style={{ width: `${Math.min(100, Math.max(0, qa.attainment_pct))}%` }}
          />
        </div>
      ) : null}
      <label className="form-field">
        Quota / target
        <input type="number" value={quota} onChange={(e) => setQuota(e.target.value)} />
      </label>
      <label className="form-field">
        Effective date
        <input type="date" value={effective || ""} onChange={(e) => setEffective(e.target.value)} />
      </label>
      <button
        type="button"
        className="btn-primary"
        disabled={busy}
        onClick={() =>
          onSave({
            personal_target: quota || 0,
            comp_effective_date: effective || null,
          })
        }
      >
        Update quota
      </button>
    </div>
  );
}

function AccessTab({ person, onSave, busy }) {
  const catalog = person.role_catalog || ["Admin", "Finance", "Manager", "Sales Rep"];
  const [role, setRole] = useState(person.role || "Sales Rep");
  const [customRole, setCustomRole] = useState(
    catalog.includes(person.role) ? "" : person.role || ""
  );
  const [perms, setPerms] = useState(
    () => new Set((person.permissions || []).filter((p) => p.granted).map((p) => p.code))
  );

  useEffect(() => {
    const roles = person.role_catalog || ["Admin", "Finance", "Manager", "Sales Rep"];
    const isSystem = roles.includes(person.role);
    setRole(isSystem ? person.role : "custom");
    setCustomRole(isSystem ? "" : person.role || "");
    setPerms(new Set((person.permissions || []).filter((p) => p.granted).map((p) => p.code)));
  }, [person]);

  const toggle = (code) => {
    const next = new Set(perms);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setPerms(next);
  };

  return (
    <div className="pe-tab">
      <h2>Access</h2>
      <label className="form-field">
        System Role
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {catalog.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
          <option value="custom">Custom role…</option>
        </select>
      </label>
      {role === "custom" ? (
        <label className="form-field">
          Custom role name
          <input value={customRole} onChange={(e) => setCustomRole(e.target.value)} />
        </label>
      ) : null}
      <h3>Permissions</h3>
      <ul className="pe-perm-list">
        {(person.permission_catalog || person.permissions || []).map((p) => {
          const checked = perms.has(p.code);
          const editable = role === "custom";
          return (
            <li key={p.code} className={checked ? "ok" : ""}>
              {editable ? (
                <label className="pe-perm-check">
                  <input type="checkbox" checked={checked} onChange={() => toggle(p.code)} />
                  {p.label}
                </label>
              ) : (
                <>
                  {checked ? "✓" : "–"} {p.label}
                </>
              )}
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        className="btn-primary"
        disabled={busy}
        onClick={() => {
          const effectiveRole = role === "custom" ? customRole.trim() || "Custom" : role;
          const payload = { role: effectiveRole };
          payload.custom_permissions = role === "custom" ? Array.from(perms) : [];
          onSave(payload);
        }}
      >
        Save access
      </button>
    </div>
  );
}

function OrdersTable({ rows, empty }) {
  if (!rows?.length) return <p className="pe-muted">{empty}</p>;
  return (
    <table className="pe-mini-table">
      <thead>
        <tr>
          <th>Order</th>
          <th>Date</th>
          <th>Amount</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((o) => (
          <tr key={o.id}>
            <td>{o.order_id}</td>
            <td>{formatDateShort(o.order_date)}</td>
            <td>{o.sales_amount}</td>
            <td>{o.order_status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TransactionsTab({ person }) {
  const tx = person.transactions || person.sales_performance || {};
  return (
    <div className="pe-tab">
      <h2>Transactions</h2>
      <dl className="pe-overview-grid">
        <div>
          <dt>Orders</dt>
          <dd>{tx.order_count ?? 0}</dd>
        </div>
        <div>
          <dt>Successful</dt>
          <dd>{tx.success_count ?? 0}</dd>
        </div>
        <div>
          <dt>Total Sales</dt>
          <dd>{tx.total_sales_display || "—"}</dd>
        </div>
      </dl>
      <h3>Recent transactions</h3>
      <OrdersTable rows={tx.recent_orders} empty="No transactions linked to this employee ID." />
    </div>
  );
}

function CommissionsTab({ person }) {
  const rows = person.commission_history || [];
  return (
    <div className="pe-tab">
      <h2>Commission History</h2>
      {rows.length === 0 ? (
        <p className="pe-muted">No commission records for this participant yet.</p>
      ) : (
        <table className="pe-mini-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Plan</th>
              <th>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{formatDateShort(r.calculated_at)}</td>
                <td>{r.plan_name || "—"}</td>
                <td>{r.amount_display || r.amount}</td>
                <td>{r.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AuditTab({ person }) {
  const rows = person.audit_log || person.activity || [];
  return (
    <div className="pe-tab">
      <h2>Audit Log</h2>
      <p className="pe-muted">Tracks user created, plan assigned, quota changed, role changed, invitations.</p>
      {rows.length === 0 ? (
        <p className="pe-muted">No audit events for this participant yet.</p>
      ) : (
        <ul className="pe-history">
          {rows.map((row) => (
            <li key={row.id}>
              <strong>{row.action}</strong>
              <span>{row.user}</span>
              <time>{formatDate(row.timestamp)}</time>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PeopleWorkspace() {
  const { personId } = useParams();
  const navigate = useNavigate();
  const { error, success, warning } = useToast();
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`user-setup/${personId}/`);
      setPerson(res.data);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load profile"));
      navigate("/user-setup");
    } finally {
      setLoading(false);
    }
  }, [personId, error, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  const patch = async (payload) => {
    setBusy(true);
    try {
      const res = await api.patch(`user-setup/${personId}/`, payload);
      setPerson(res.data);
      success("Participant updated");
    } catch (err) {
      error(getApiErrorMessage(err, "Update failed"));
    } finally {
      setBusy(false);
    }
  };

  const inviteAction = async (action) => {
    setBusy(true);
    try {
      const res = await api.post(`user-setup/${personId}/invite/`, { action });
      if (action === "copy_link" || (action === "resend" && res.data.invite_link)) {
        const link = res.data.invite_link;
        if (link) {
          await navigator.clipboard?.writeText(link).catch(() => {});
          success(action === "copy_link" ? "Invite link copied" : "Invite resent — link copied");
        } else if (action === "resend" && res.data.sent) {
          success("Invitation resent");
        } else {
          warning(res.data.invite_error || "Invite link unavailable");
        }
      } else if (action === "resend") {
        if (res.data.sent) success("Invitation resent");
        else warning(res.data.invite_error || "Invite could not be sent");
      } else if (action === "revoke") {
        success("Invitation revoked");
      }
      await load();
    } catch (err) {
      error(getApiErrorMessage(err, "Invite action failed"));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !person) return <LoadingCenter minHeight={280} />;
  if (!person) return null;

  return (
    <div className="pe-workspace">
      <div className="pe-workspace__top">
        <button type="button" className="cp-btn-ghost" onClick={() => navigate("/user-setup")}>
          ← Participant Management
        </button>
        <div className="pe-workspace__identity">
          <div className="pe-avatar" aria-hidden>
            {(person.display_name || person.name || "?").slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h1>{person.display_name || person.name}</h1>
            <div className="pe-identity-meta">
              <span>{person.employee_id || "No ID"}</span>
              <span>{person.position || person.position_name || "No position"}</span>
              <span>{person.role || "—"}</span>
              <span>{person.territory_name || "No territory"}</span>
              <StatusBadge code={person.status} label={person.status_label} />
            </div>
          </div>
        </div>
      </div>
      <div className="pe-workspace__body">
        <nav className="pe-workspace__nav" aria-label="Profile sections">
          <ul>
            {TABS.map((tab) => (
              <li key={tab.to}>
                <NavLink
                  to={`/user-setup/${personId}/${tab.to}`}
                  className={({ isActive }) => `pe-workspace__link${isActive ? " is-active" : ""}`}
                >
                  {tab.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="pe-workspace__content">
          <Routes>
            <Route index element={<Navigate to="overview" replace />} />
            <Route
              path="overview"
              element={
                <OverviewTab
                  person={person}
                  busy={busy}
                  onResend={() => inviteAction("resend")}
                  onRevoke={() => inviteAction("revoke")}
                  onCopyLink={() => inviteAction("copy_link")}
                />
              }
            />
            <Route path="organization" element={<OrganizationTab person={person} />} />
            <Route
              path="compensation"
              element={<CompensationTab person={person} onSave={patch} busy={busy} />}
            />
            <Route path="quota" element={<QuotaTab person={person} onSave={patch} busy={busy} />} />
            <Route path="commissions" element={<CommissionsTab person={person} />} />
            <Route path="transactions" element={<TransactionsTab person={person} />} />
            <Route path="access" element={<AccessTab person={person} onSave={patch} busy={busy} />} />
            <Route path="audit" element={<AuditTab person={person} />} />
            <Route path="activity" element={<Navigate to="../audit" replace />} />
            <Route path="performance" element={<Navigate to="../transactions" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

export default PeopleWorkspace;
