import { useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import MonthPickerField from "../Components/MonthPickerField";
import { BUSINESS_GROUP_OPTIONS } from "../utils/businessGroups";

const INITIAL_FORM = {
  plan_name: "",
  description: "",
  comp_period: "",
  status: "Active",
  pay_period_type: "Monthly",
  plan_basis: "Role",
  position_name: "",
  role: "",
  title: "",
  business_group: "",
  table_type: "rate",
  default_commission_rate: "",
};

function PlanHeaderForm({ onPlanCreated, onCancel }) {
  const { error } = useToast();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(INITIAL_FORM);

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
    if (!form.comp_period) {
      error("Compensation month is required");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        plan_name: form.plan_name.trim(),
        role: form.role.trim(),
        status: form.status || "Active",
        plan_basis: form.plan_basis || "Role",
        comp_period: form.comp_period,
        pay_period_type: "Monthly",
        commission_table_type:
          form.table_type === "flat"
            ? "FLAT"
            : form.table_type === "lookup"
              ? "LOOKUP"
              : "RATE",
        description: form.description || "",
        position_name: form.position_name || "",
        title: form.title || "",
        business_group: form.business_group || "",
      };

      const defaultRate = parseFloat(form.default_commission_rate);
      if (form.table_type === "rate" && !Number.isNaN(defaultRate) && defaultRate > 0) {
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
      if (form.table_type === "flat" && !Number.isNaN(defaultRate) && defaultRate > 0) {
        payload.sc_flat_rate_tables = [
          {
            flat_rate: defaultRate,
            is_active: true,
          },
        ];
      }

      const res = await api.post("compensation-plans/", payload);
      if (onPlanCreated) onPlanCreated(res.data);
      setForm(INITIAL_FORM);
    } catch (err) {
      const data = err.response?.data;
      const msg = getApiErrorMessage(err, "Error creating compensation plan");
      error(msg);
    } finally {
      setLoading(false);
    }
  };

  const req = { color: "var(--danger-color)" };

  return (
    <div className="panel">
      <h2 className="panel__title">Create new compensation plan</h2>
      <p style={{ color: "var(--text-muted)", marginTop: 0, marginBottom: 20, fontSize: 14 }}>
        Required fields are marked with *. Role must match User Setup. Pick the month this plan
        applies to — orders only match plans in the same calendar month.
      </p>

      <div className="form-grid">
        <div className="form-field">
          <label>Plan name <span style={req}>*</span></label>
          <input name="plan_name" value={form.plan_name} onChange={handleChange} placeholder="Sales Rep — June 2026" />
        </div>
        <div className="form-field">
          <label>Role <span style={req}>*</span></label>
          <input name="role" value={form.role} onChange={handleChange} placeholder="Sales Rep" />
        </div>
        <div className="form-field">
          <MonthPickerField
            label="Compensation month *"
            value={form.comp_period}
            onChange={(value) => setForm({ ...form, comp_period: value })}
            disabled={loading}
            required
            helperText="Plan applies only to orders in this month (1st through last day)."
          />
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
        <div className="form-field">
          <label>Commission table <span style={req}>*</span></label>
          <select name="table_type" value={form.table_type} onChange={handleChange}>
            <option value="rate">SC Rate Table (% by sales band)</option>
            <option value="flat">SC Flat Rate Table (single %)</option>
            <option value="lookup">SC Lookup Table (product / service / distribution)</option>
          </select>
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
        {form.table_type !== "lookup" && (
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
        <div className="form-field">
          <label>Position name (optional)</label>
          <input name="position_name" value={form.position_name} onChange={handleChange} placeholder="Leave blank for role-wide plan" />
        </div>
        <div className="form-field">
          <label>Description (optional)</label>
          <input name="description" value={form.description} onChange={handleChange} />
        </div>
      </div>

      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
        )}
        <button type="button" className="btn-primary" onClick={savePlan} disabled={loading}>
          {loading ? "Creating…" : "Create plan"}
        </button>
      </div>
    </div>
  );
}

export default PlanHeaderForm;
