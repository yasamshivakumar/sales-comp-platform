import { NavLink, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import DatePickerField from "../Components/DatePickerField";
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

function formatMoneyOrRate(value, unit) {
  if (value == null || value === "") return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  if (unit === "percent") return `${num}%`;
  if (unit === "multiplier") return `${num}×`;
  if (unit === "boolean") return num > 0 ? "Eligible" : "Not eligible";
  return num.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function OverrideStatusBadge({ status }) {
  const tone =
    status === "approved"
      ? "success"
      : status === "pending_approval" || status === "draft"
        ? "warning"
        : status === "rejected" || status === "revoked"
          ? "danger"
          : "neutral";
  return <span className={`pe-badge pe-badge--${tone}`}>{(status || "—").replace(/_/g, " ")}</span>;
}

function OverrideFormModal({ person, plans, choices, initial, onClose, onSaved }) {
  const { error, success } = useToast();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(() => ({
    name: initial?.name || `${person.name || "Employee"} Override`,
    compensation_plan: String(initial?.compensation_plan || person.assigned_plan_id || ""),
    override_type: initial?.override_type || "commission_rate",
    value: initial?.value ?? "",
    value_unit: initial?.value_unit || "percent",
    previous_value: initial?.previous_value ?? "",
    effective_from: initial?.effective_from || new Date().toISOString().slice(0, 10),
    effective_to: initial?.effective_to || "",
    reason: initial?.reason || "",
    approval_required: initial?.approval_required ?? true,
    approver: initial?.approver || "",
    stop_on_match: initial?.stop_on_match ?? true,
  }));

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const onTypeChange = (type) => {
    const meta = (choices.override_types || []).find((row) => row.value === type);
    setForm((prev) => ({
      ...prev,
      override_type: type,
      value_unit: meta?.default_unit || prev.value_unit,
    }));
  };

  const submit = async (approveNow = false) => {
    setBusy(true);
    try {
      const payload = {
        ...form,
        employee: person.id,
        compensation_plan: form.compensation_plan || null,
        approver: form.approver || null,
        previous_value: form.previous_value === "" ? null : form.previous_value,
        value: form.value === "" ? null : form.value,
        effective_to: form.effective_to || null,
      };
      let res;
      if (initial?.id) {
        res = await api.patch(`compensation-overrides/${initial.id}/`, payload);
      } else {
        res = await api.post("compensation-overrides/", payload);
      }
      let row = res.data;
      if (approveNow && row.status !== "approved") {
        if (row.status === "draft") {
          await api.post(`compensation-overrides/${row.id}/action/`, { action: "submit" });
        }
        row = (
          await api.post(`compensation-overrides/${row.id}/action/`, {
            action: "approve",
            reason: form.reason || "Approved on create",
          })
        ).data;
      }
      success(approveNow ? "Override approved" : initial?.id ? "Override updated" : "Override created");
      onSaved(row);
    } catch (err) {
      error(getApiErrorMessage(err, "Could not save override"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pe-modal" role="dialog" aria-modal="true">
      <div className="pe-modal__backdrop" onClick={onClose} />
      <div className="pe-modal__panel pe-override-modal">
        <header className="pe-modal__header">
          <div>
            <p className="pe-eyebrow">Employee exception</p>
            <h3>{initial?.id ? "Edit override" : "Create override"}</h3>
          </div>
          <button type="button" className="cp-btn-ghost" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="pe-modal__body pe-override-form">
          <label className="form-field">
            Override name
            <input value={form.name} onChange={(e) => set("name", e.target.value)} />
          </label>
          <label className="form-field">
            Compensation plan
            <select
              value={form.compensation_plan}
              onChange={(e) => set("compensation_plan", e.target.value)}
            >
              <option value="">Employee's assigned plan</option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.plan_name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Override type
            <select value={form.override_type} onChange={(e) => onTypeChange(e.target.value)}>
              {(choices.override_types || []).map((row) => (
                <option key={row.value} value={row.value}>
                  {row.label}
                </option>
              ))}
            </select>
          </label>
          <div className="pe-form-row">
            <label className="form-field">
              Value
              <input
                type="number"
                step="any"
                value={form.value}
                onChange={(e) => set("value", e.target.value)}
                placeholder="e.g. 3"
              />
            </label>
            <label className="form-field">
              Unit
              <select value={form.value_unit} onChange={(e) => set("value_unit", e.target.value)}>
                {(choices.value_units || []).map((row) => (
                  <option key={row.value} value={row.value}>
                    {row.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field">
              Previous / plan value
              <input
                type="number"
                step="any"
                value={form.previous_value}
                onChange={(e) => set("previous_value", e.target.value)}
                placeholder="optional"
              />
            </label>
          </div>
          <div className="pe-form-row">
            <label className="form-field">
              Effective from
              <DatePickerField
                label="Effective from"
                hideLabel
                value={form.effective_from}
                onChange={(value) => set("effective_from", value)}
                maxDate={form.effective_to || undefined}
              />
            </label>
            <label className="form-field">
              Effective to
              <DatePickerField
                label="Effective to"
                hideLabel
                value={form.effective_to}
                onChange={(value) => set("effective_to", value)}
                minDate={form.effective_from || undefined}
              />
            </label>
          </div>
          <label className="form-field">
            Reason
            <textarea
              rows={3}
              value={form.reason}
              onChange={(e) => set("reason", e.target.value)}
              placeholder="e.g. Promotion Incentive"
            />
          </label>
          <div className="pe-form-row">
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={form.approval_required}
                onChange={(e) => set("approval_required", e.target.checked)}
              />
              Approval required
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={form.stop_on_match}
                onChange={(e) => set("stop_on_match", e.target.checked)}
              />
              Skip plan rules when applied
            </label>
          </div>
          {form.approval_required ? (
            <label className="form-field">
              Approver
              <select value={form.approver} onChange={(e) => set("approver", e.target.value)}>
                <option value="">— Select —</option>
                {(choices.approvers || []).map((row) => (
                  <option key={row.value} value={row.value}>
                    {row.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <footer className="pe-modal__footer">
          <button type="button" className="btn-secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => submit(false)}>
            Save as draft
          </button>
          <button type="button" className="btn-primary" disabled={busy} onClick={() => submit(true)}>
            Save &amp; approve
          </button>
        </footer>
      </div>
    </div>
  );
}

function CompensationTab({ person, onSave, busy }) {
  const { error, success } = useToast();
  const pc = person.participant_compensation || {};
  const [eligible, setEligible] = useState(Boolean(pc.commission_eligible ?? person.commission_eligible));
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(
    String(person.assigned_plan_id || pc.assigned_plan?.id || "")
  );
  const [comp, setComp] = useState(null);
  const [choices, setChoices] = useState({ override_types: [], value_units: [], approvers: [] });
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // null | 'create' | override object
  const [assignedRules, setAssignedRules] = useState([]);
  const [rulesError, setRulesError] = useState("");

  const loadCompensation = useCallback(async () => {
    setLoading(true);
    setRulesError("");
    try {
      const [compRes, choiceRes, planRes, rulesRes] = await Promise.all([
        api.get(`user-setup/${person.id}/compensation/`),
        api.get("compensation-overrides/choices/"),
        api.get("compensation-plans/", { params: { page_size: 100, status: "Active" } }),
        api.get(`user-setup/${person.id}/commission-rules/`).catch(() => null),
      ]);
      setComp(compRes.data);
      setChoices(choiceRes.data || {});
      const data = planRes.data;
      setPlans(Array.isArray(data) ? data : data?.results || []);
      if (rulesRes?.data) {
        const rows = Array.isArray(rulesRes.data?.results)
          ? rulesRes.data.results
          : Array.isArray(rulesRes.data)
            ? rulesRes.data
            : [];
        setAssignedRules(rows);
      } else {
        setAssignedRules(
          compRes.data?.assigned_commission_rules ||
            compRes.data?.effective_rules ||
            []
        );
      }
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load compensation"));
      setRulesError(getApiErrorMessage(err, "Failed to load commission rules"));
    } finally {
      setLoading(false);
    }
  }, [person.id, error]);

  useEffect(() => {
    setEligible(Boolean(pc.commission_eligible ?? person.commission_eligible));
    setPlanId(String(person.assigned_plan_id || pc.assigned_plan?.id || ""));
  }, [person, pc]);

  useEffect(() => {
    loadCompensation();
  }, [loadCompensation]);

  const runAction = async (overrideId, action, reason = "") => {
    try {
      await api.post(`compensation-overrides/${overrideId}/action/`, { action, reason });
      success(`Override ${action}d`);
      loadCompensation();
    } catch (err) {
      error(getApiErrorMessage(err, `Could not ${action} override`));
    }
  };

  const removeOverride = async (overrideId) => {
    try {
      await api.delete(`compensation-overrides/${overrideId}/`, {
        params: { reason: "Removed from employee compensation tab" },
      });
      success("Override removed");
      loadCompensation();
    } catch (err) {
      error(getApiErrorMessage(err, "Could not remove override"));
    }
  };

  if (loading && !comp) {
    return (
      <div className="pe-tab">
        <LoadingCenter label="Loading compensation…" />
      </div>
    );
  }

  const assigned = comp?.assigned_plan;
  const overrides = comp?.overrides || [];
  const history = comp?.history || [];
  const activeOverrides = overrides.filter((row) => row.is_active_now);

  const formatRuleRate = (rule) => {
    const results = rule.results || [];
    if (!results.length) return "—";
    return results
      .map((r) => {
        const label = r.rate_type_label || r.rate_type || "Result";
        if (r.rate_value == null || r.rate_value === "") return label;
        const isPct =
          String(r.rate_type || "").includes("pct") ||
          String(r.rate_type || "") === "percentage" ||
          String(r.rate_type_label || "").toLowerCase().includes("%");
        return `${label}: ${r.rate_value}${isPct ? "%" : ""}`;
      })
      .join(", ");
  };

  const formatRuleConditions = (rule) => {
    const conditions = rule.conditions || [];
    if (!conditions.length) return "All Orders";
    const joiner = rule.condition_logic === "or" ? " OR " : " AND ";
    return conditions
      .map(
        (c) =>
          `${c.field_label || c.field} ${c.operator_label || c.operator} ${c.value || ""}`.trim()
      )
      .join(joiner);
  };

  return (
    <div className="pe-tab pe-comp-tab">
      <div className="pe-tab__actions">
        <h2>Compensation</h2>
        <button type="button" className="btn-primary" onClick={() => setModal("create")}>
          + Create override
        </button>
      </div>

      <section className="pe-comp-section">
        <h3>Assigned Compensation Plan</h3>
        <div className="pe-participant-card">
          <div>
            <span className="pe-expand__label">Plan</span>
            <strong>{assigned?.name || pc.assigned_plan_name || "— Unassigned —"}</strong>
          </div>
          <div>
            <span className="pe-expand__label">Status</span>
            <strong>{assigned?.status || "—"}</strong>
          </div>
          <div>
            <span className="pe-expand__label">Table type</span>
            <strong>{assigned?.commission_table_type || pc.calculation_method || "—"}</strong>
          </div>
          <div>
            <span className="pe-expand__label">Effective</span>
            <strong>
              {assigned?.effective_start_date
                ? `${formatDate(assigned.effective_start_date)} – ${
                    assigned.effective_end_date
                      ? formatDate(assigned.effective_end_date)
                      : "Open"
                  }`
                : pc.effective_period || "—"}
            </strong>
          </div>
          <div>
            <span className="pe-expand__label">Eligibility</span>
            <strong className={eligible ? "pe-yes" : "pe-no"}>{eligible ? "YES" : "NO"}</strong>
          </div>
          <div>
            <span className="pe-expand__label">Assignment</span>
            <strong>
              {assigned?.is_explicit_assignment ? "Explicit" : assigned ? "Inherited" : "—"}
            </strong>
          </div>
        </div>
        <div className="pe-comp-assign">
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
            onClick={async () => {
              await onSave({
                commission_eligible: eligible,
                assigned_plan_id: planId || null,
              });
              loadCompensation();
            }}
          >
            Save assignment
          </button>
        </div>
      </section>

      <section className="pe-comp-section">
        <div className="pe-comp-section__head">
          <div>
            <h3>Commission Rules</h3>
            <p className="pe-muted">
              Rules explicitly assigned to this employee from Commission Rules. Updates appear
              when you open or refresh this tab.
            </p>
          </div>
          <NavLink className="btn-secondary" to="/commission-rules">
            Manage rules
          </NavLink>
        </div>

        {loading ? (
          <p className="pe-muted">Loading commission rules…</p>
        ) : rulesError ? (
          <p className="pe-muted pe-comp-rules-error">{rulesError}</p>
        ) : assignedRules.length === 0 ? (
          <div className="pe-comp-empty">
            <span>No commission rules are assigned to this employee.</span>
            <NavLink className="btn-secondary" to="/commission-rules">
              Open Commission Rules
            </NavLink>
          </div>
        ) : (
          <ul className="pe-rule-list">
            {assignedRules.map((rule) => (
              <li key={rule.id} className="pe-rule-card">
                <div className="pe-rule-card__title">
                  <strong>✓ {rule.name}</strong>
                    <span
                      className={`pe-rule-card__status ${
                        rule.is_active === false ? "is-inactive" : "is-active"
                      }`}
                    >
                      {rule.status || (rule.is_active === false ? "Inactive" : "Active")}
                    </span>
                  </div>
                  {rule.assignment_source === "plan_participants" ||
                  rule.apply_to_all_plan_participants ? (
                    <p className="pe-muted" style={{ marginTop: 0, marginBottom: 10 }}>
                      Applies to all participants on this Compensation Plan
                    </p>
                  ) : null}
                <dl className="pe-rule-card__meta">
                  <div>
                    <dt>Compensation Plan</dt>
                    <dd>{rule.compensation_plan_name || assigned?.name || "—"}</dd>
                  </div>
                  <div>
                    <dt>Rule Type</dt>
                    <dd>{rule.rule_type_label || rule.rule_type || "—"}</dd>
                  </div>
                  <div>
                    <dt>Commission Rate / Result</dt>
                    <dd>{formatRuleRate(rule)}</dd>
                  </div>
                  <div>
                    <dt>Conditions</dt>
                    <dd>{formatRuleConditions(rule)}</dd>
                  </div>
                  <div>
                    <dt>Valid From</dt>
                    <dd>{formatDateShort(rule.effective_start_date)}</dd>
                  </div>
                  <div>
                    <dt>Valid To</dt>
                    <dd>
                      {rule.effective_end_date
                        ? formatDateShort(rule.effective_end_date)
                        : "Open"}
                    </dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{formatDateShort(rule.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Assigned</dt>
                    <dd>{formatDateShort(rule.assigned_at)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="pe-comp-section">
        <div className="pe-tab__actions">
          <h3>Employee Overrides</h3>
          <span className="pe-muted">
            {activeOverrides.length} active · {overrides.length} total
          </span>
        </div>
        {overrides.length === 0 ? (
          <div className="pe-comp-empty">
            <p>No employee overrides. Plan rules apply as written.</p>
            <button type="button" className="btn-secondary" onClick={() => setModal("create")}>
              Create the first override
            </button>
          </div>
        ) : (
          <div className="enterprise-table-wrap">
            <table className="enterprise-table pe-comp-table">
              <thead>
                <tr>
                  <th>Override</th>
                  <th>Type</th>
                  <th>Value</th>
                  <th>Effective</th>
                  <th>Status</th>
                  <th>Reason</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {overrides.map((row) => (
                  <tr key={row.id} className={row.is_active_now ? "is-active-override" : ""}>
                    <td>
                      <strong>{row.name}</strong>
                      {row.is_active_now ? (
                        <div className="pe-table__sub pe-yes">Active now · Priority {row.priority}</div>
                      ) : null}
                    </td>
                    <td>{row.override_type_label}</td>
                    <td>{formatMoneyOrRate(row.value, row.value_unit)}</td>
                    <td>
                      {formatDate(row.effective_from)}
                      {" – "}
                      {row.effective_to ? formatDate(row.effective_to) : "Open"}
                    </td>
                    <td>
                      <OverrideStatusBadge status={row.status} />
                    </td>
                    <td>{row.reason || "—"}</td>
                    <td className="pe-comp-actions">
                      {row.status === "draft" || row.status === "pending_approval" ? (
                        <button
                          type="button"
                          className="cp-btn-ghost"
                          onClick={() => runAction(row.id, "approve", row.reason)}
                        >
                          Approve
                        </button>
                      ) : null}
                      <button type="button" className="cp-btn-ghost" onClick={() => setModal(row)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="cp-btn-ghost pe-danger-link"
                        onClick={() => removeOverride(row.id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="pe-comp-section">
        <h3>Override History</h3>
        {history.length === 0 ? (
          <p className="pe-muted">No override events yet.</p>
        ) : (
          <ul className="pe-comp-history">
            {history.map((event) => (
              <li key={event.id}>
                <div className="pe-comp-history__meta">
                  <strong>{event.event_label}</strong>
                  <span>{formatDate(event.created_at)}</span>
                </div>
                <div className="pe-comp-history__body">
                  <span>{event.override_name}</span>
                  <span>· {event.actor_name}</span>
                  {event.reason ? <span>· {event.reason}</span> : null}
                </div>
                {(event.old_value?.value != null || event.new_value?.value != null) && (
                  <div className="pe-table__sub">
                    {event.old_value?.value != null ? `Was ${event.old_value.value}` : "Created"}
                    {event.new_value?.value != null ? ` → ${event.new_value.value}` : ""}
                    {event.effective_from
                      ? ` · ${formatDate(event.effective_from)} – ${
                          event.effective_to ? formatDate(event.effective_to) : "Open"
                        }`
                      : ""}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {modal ? (
        <OverrideFormModal
          person={person}
          plans={plans}
          choices={choices}
          initial={modal === "create" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null);
            loadCompensation();
          }}
        />
      ) : null}
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
        <DatePickerField
          label="Effective date"
          hideLabel
          value={effective || ""}
          onChange={(value) => setEffective(value)}
        />
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
