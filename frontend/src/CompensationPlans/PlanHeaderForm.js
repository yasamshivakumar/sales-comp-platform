import { useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import { BUSINESS_GROUP_OPTIONS } from "../utils/businessGroups";

const INITIAL_FORM = {
  plan_name: "",
  description: "",
  effective_from: "",
  effective_to: "",
  status: "Active",
  pay_period_type: "Monthly",
  plan_basis: "Role",
  plan_type: "sales_commission",
  owner: "",
  approver: "",
  position_name: "",
  role: "",
  title: "",
  business_group: "",
  table_type: "rate",
  default_commission_rate: "",
};

function dateFromValue(dateValue) {
  if (!dateValue) return "";
  return String(dateValue).slice(0, 10);
}

function tableTypeFromPlan(plan) {
  const type = String(plan?.commission_table_type || "RATE").toUpperCase();
  if (type === "FLAT") return "flat";
  if (type === "LOOKUP") return "lookup";
  if (type === "HIGHEST") return "highest";
  if (type === "MARGINAL") return "marginal";
  return "rate";
}

export function commissionTableLabel(type) {
  const value = String(type || "").toUpperCase();
  if (value === "HIGHEST") return "Highest Rate";
  if (value === "MARGINAL") return "Marginal Rate";
  if (value === "FLAT") return "Flat Rate";
  if (value === "LOOKUP") return "Lookup";
  if (value === "RATE") return "Rate";
  return value || "—";
}

function formFromPlan(plan) {
  if (!plan) return INITIAL_FORM;
  const version = plan.current_version;
  return {
    plan_name: plan.plan_name || "",
    description: plan.description || "",
    effective_from: dateFromValue(
      version?.effective_from || plan.effective_start_date
    ),
    effective_to: dateFromValue(
      version?.effective_to || plan.effective_end_date
    ),
    status: plan.status || "Active",
    pay_period_type: plan.pay_period_type || "Monthly",
    plan_basis: plan.plan_basis || "Role",
    plan_type: plan.plan_type || "sales_commission",
    owner: plan.owner || "",
    approver: plan.approver || "",
    position_name: plan.position_name || "",
    role: plan.role || "",
    title: plan.title || "",
    business_group: plan.business_group || "",
    table_type: tableTypeFromPlan(plan),
    default_commission_rate: "",
  };
}

function PlanHeaderForm({ initialPlan = null, onPlanCreated, onPlanUpdated, onCancel }) {
  const { error } = useToast();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(() => formFromPlan(initialPlan));
  const editing = Boolean(initialPlan?.id);

  useEffect(() => {
    setForm(formFromPlan(initialPlan));
  }, [initialPlan]);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const savePlan = async () => {
    if (!form.plan_name.trim()) {
      error("Plan name is required");
      return;
    }
    if (!form.role.trim()) {
      error("Role is required (must match employee role in User Setup)");
      return;
    }
    if (!form.effective_from) {
      error("Effective from date is required");
      return;
    }
    if (form.effective_to && form.effective_to < form.effective_from) {
      error("Effective to cannot be before effective from");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        plan_name: form.plan_name.trim(),
        role: form.role.trim(),
        status: form.status || "Active",
        plan_basis: form.plan_basis || "Role",
        plan_type: form.plan_type || "sales_commission",
        owner: form.owner || "",
        approver: form.approver || "",
        effective_start_date: form.effective_from,
        effective_end_date: form.effective_to || null,
        pay_period_type: form.pay_period_type || "Monthly",
        commission_table_type:
          form.table_type === "flat"
            ? "FLAT"
            : form.table_type === "lookup"
              ? "LOOKUP"
              : form.table_type === "highest"
                ? "HIGHEST"
                : form.table_type === "marginal"
                  ? "MARGINAL"
                  : "RATE",
        description: form.description || "",
        position_name: form.position_name || "",
        title: form.title || "",
        business_group: form.business_group || "",
      };

      const defaultRate = parseFloat(form.default_commission_rate);
      if (
        !editing &&
        (form.table_type === "rate" ||
          form.table_type === "highest" ||
          form.table_type === "marginal") &&
        !Number.isNaN(defaultRate) &&
        defaultRate > 0
      ) {
        payload.sc_rate_tables = [
          {
            tier_name: "Default",
            from_amount: 0,
            to_amount: null,
            commission_rate: defaultRate,
            bonus_amount: 0,
            sequence: 1,
            is_active: true,
          },
        ];
      }
      if (!editing && form.table_type === "flat" && !Number.isNaN(defaultRate) && defaultRate > 0) {
        payload.sc_flat_rate_tables = [
          {
            flat_rate: defaultRate,
            minimum_sales_threshold: 0,
            bonus_amount: 0,
            is_active: true,
          },
        ];
      }

      if (editing) {
        const res = await api.patch(`compensation-plans/${initialPlan.id}/`, payload);
        if (onPlanUpdated) onPlanUpdated(res.data);
      } else {
        const res = await api.post("compensation-plans/", payload);
        if (onPlanCreated) onPlanCreated(res.data);
        setForm(INITIAL_FORM);
      }
    } catch (err) {
      const msg = getApiErrorMessage(err, "Error creating compensation plan");
      error(msg);
    } finally {
      setLoading(false);
    }
  };

  const req = { color: "var(--danger-color)" };

  return (
    <div className="panel cp-form-card">
      <h2 className="panel__title">
        {editing ? "Edit compensation plan" : "Create new compensation plan"}
      </h2>
      <p className="cp-toolbar__hint" style={{ marginTop: 0, marginBottom: 12 }}>
        {editing
          ? "Update plan identity and the draft version’s effective dates. Published versions are read-only — clone a version to change rates."
          : "Create one plan for a role/position. Set the first version’s effective date range (can be a quarter or full year). You do not need a new plan every month."}
      </p>
      <div className="plan-workflow-callout">
        <strong>Plan vs month:</strong> the plan is the identity (e.g. “Sales Executive”).
        Dates belong to a <em>version</em>. Monthly quotas go on the version later —
        not as a separate plan per month.
      </div>

      <div className="cp-form-section">
        <h3 className="cp-form-section__title">Identity</h3>
      <div className="form-grid">
        <div className="form-field">
          <label>Plan name <span style={req}>*</span></label>
          <input name="plan_name" value={form.plan_name} onChange={handleChange} placeholder="Sales Executive Plan" />
        </div>
        <div className="form-field">
          <label>Plan type</label>
          <select name="plan_type" value={form.plan_type} onChange={handleChange}>
            <option value="sales_commission">Sales Commission</option>
            <option value="bonus_plan">Bonus Plan</option>
            <option value="manager_override">Manager Override</option>
            <option value="channel_incentive">Channel Incentive</option>
            <option value="spiff">SPIFF</option>
          </select>
        </div>
        <div className="form-field">
          <label>Owner</label>
          <input name="owner" value={form.owner} onChange={handleChange} placeholder="Sales Operations" />
        </div>
        <div className="form-field">
          <label>Approver</label>
          <input name="approver" value={form.approver} onChange={handleChange} placeholder="Finance Director" />
        </div>
        <div className="form-field">
          <label>Role <span style={req}>*</span></label>
          <input name="role" value={form.role} onChange={handleChange} placeholder="Sales Rep" />
        </div>
        <div className="form-field">
          <label>Position name (optional)</label>
          <input name="position_name" value={form.position_name} onChange={handleChange} placeholder="Leave blank for role-wide plan" />
        </div>
        <div className="form-field">
          <label>Description (optional)</label>
          <input name="description" value={form.description} onChange={handleChange} />
        </div>
      </div>
      </div>

      <div className="cp-form-section">
        <h3 className="cp-form-section__title">Effective period</h3>
      <div className="form-grid">
        <div className="form-field">
          <label>Effective from <span style={req}>*</span></label>
          <input
            type="date"
            name="effective_from"
            value={form.effective_from}
            onChange={handleChange}
            disabled={loading}
            required
          />
          <small style={{ color: "var(--text-muted)", fontSize: 12 }}>
            First day Version 1 applies to orders.
          </small>
        </div>
        <div className="form-field">
          <label>Effective to</label>
          <input
            type="date"
            name="effective_to"
            value={form.effective_to}
            onChange={handleChange}
            disabled={loading}
          />
          <small style={{ color: "var(--text-muted)", fontSize: 12 }}>
            Leave blank for open-ended (until you publish a newer version).
          </small>
        </div>
        <div className="form-field">
          <label>Status <span style={req}>*</span></label>
          <select name="status" value={form.status} onChange={handleChange}>
            <option>Active</option>
            <option>Draft</option>
            <option>Inactive</option>
          </select>
        </div>
        <div className="form-field">
          <label>Plan basis <span style={req}>*</span></label>
          <select name="plan_basis" value={form.plan_basis} onChange={handleChange}>
            <option>Role</option>
            <option>Product</option>
            <option>Service</option>
            <option>Individual</option>
            <option>Region</option>
            <option>Customer Segment</option>
          </select>
        </div>
      </div>
      </div>

      <div className="cp-form-section">
        <h3 className="cp-form-section__title">Commission table</h3>
      <div className="form-grid">
        <div className="form-field">
          <label>Commission table <span style={req}>*</span></label>
          <select name="table_type" value={form.table_type} onChange={handleChange}>
            <option value="rate">SC Rate Table (% by sales band, per order)</option>
            <option value="highest">Highest Rate Table (monthly total tier %)</option>
            <option value="marginal">Marginal Rate Table (bands fill across orders)</option>
            <option value="flat">SC Flat Rate Table (single %)</option>
            <option value="lookup">SC Lookup Table (product / service / distribution)</option>
          </select>
          {form.table_type === "highest" && (
            <small style={{ color: "var(--text-muted)", fontSize: 12, display: "block", marginTop: 6 }}>
              Monthly successful sales are summed first. The matching tier’s rate then applies to the
              entire monthly total (not per order).
            </small>
          )}
          {form.table_type === "marginal" && (
            <small style={{ color: "var(--text-muted)", fontSize: 12, display: "block", marginTop: 6 }}>
              Bands fill up as orders come in. Each order first tops up the leftover room in the
              current band at that band’s rate, then the rest of the order is paid at the next
              band’s rate. The top band is open-ended.
            </small>
          )}
          {form.table_type === "rate" && (
            <small style={{ color: "var(--text-muted)", fontSize: 12, display: "block", marginTop: 6 }}>
              Each order picks its own tier band; the monthly commission is the sum of those
              per-order commissions.
            </small>
          )}
        </div>
        <div className="form-field">
          <label>Business group / currency</label>
          <select name="business_group" value={form.business_group} onChange={handleChange}>
            <option value="">Use order currency</option>
            {BUSINESS_GROUP_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} ({option.currency})
              </option>
            ))}
          </select>
          <small style={{ color: "var(--text-muted)", fontSize: 12 }}>
            Used to show rule bonus amounts in the right currency.
          </small>
        </div>
        {!editing && form.table_type !== "lookup" && (
        <div className="form-field">
          <label>
            Default commission rate %{" "}
            <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(recommended)</span>
          </label>
          <input
            type="number"
            name="default_commission_rate"
            value={form.default_commission_rate}
            onChange={handleChange}
            placeholder="e.g. 5"
            min="0"
            step="0.01"
          />
          <small style={{ color: "var(--text-muted)", fontSize: 12 }}>
            Creates the first rate tier so commissions calculate immediately.
          </small>
        </div>
        )}
      </div>
      </div>

      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
        )}
        <button type="button" className="btn-primary" onClick={savePlan} disabled={loading}>
          {loading ? (editing ? "Saving…" : "Creating…") : editing ? "Save changes" : "Create plan"}
        </button>
      </div>
    </div>
  );
}

export default PlanHeaderForm;
