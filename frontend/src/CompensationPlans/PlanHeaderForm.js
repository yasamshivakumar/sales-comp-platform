import { useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";

const INITIAL_FORM = {
  plan_name: "",
  description: "",
  effective_start_date: "",
  effective_end_date: "",
  status: "Active",
  pay_period_type: "Monthly",
  plan_basis: "Role",
  position_name: "",
  role: "",
  title: "",
  business_group: "",
  table_type: "rate",
};

function PlanHeaderForm({ onPlanCreated }) {
  const { success, error } = useToast();
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
    if (!form.effective_start_date) {
      error("Effective start date is required");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        plan_name: form.plan_name.trim(),
        role: form.role.trim(),
        status: form.status || "Active",
        plan_basis: form.plan_basis || "Role",
        effective_start_date: form.effective_start_date,
        commission_table_type:
          form.table_type === "flat" ? "FLAT" : "RATE",
        description: form.description || "",
        effective_end_date: form.effective_end_date || null,
        pay_period_type: form.pay_period_type || "Monthly",
        position_name: form.position_name || "",
        title: form.title || "",
        business_group: form.business_group || "",
      };

      const res = await api.post("compensation-plans/", payload);
      success("Compensation plan created successfully!");
      if (onPlanCreated) onPlanCreated(res.data);
      setForm(INITIAL_FORM);
    } catch (err) {
      const data = err.response?.data;
      const msg =
        (typeof data === "object" && data && Object.values(data).flat().join(", ")) ||
        data?.error ||
        "Error creating compensation plan";
      error(msg);
    } finally {
      setLoading(false);
    }
  };

  const req = { color: "var(--danger-color)" };

  return (
    <div className="panel">
      <h2 className="panel__title">Create compensation plan</h2>
      <p className="orders-section__desc" style={{ marginBottom: "1rem" }}>
        Required: plan name, role, status Active, plan basis Role, effective start date,
        commission table type. All other fields are optional.
      </p>

      <div className="form-grid">
        <div className="form-field">
          <label>Plan name <span style={req}>*</span></label>
          <input name="plan_name" value={form.plan_name} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Role <span style={req}>*</span></label>
          <input name="role" value={form.role} onChange={handleChange} placeholder="Sales Rep" />
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
          <label>Effective start <span style={req}>*</span></label>
          <input type="date" name="effective_start_date" value={form.effective_start_date} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Effective end (optional)</label>
          <input type="date" name="effective_end_date" value={form.effective_end_date} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Commission table <span style={req}>*</span></label>
          <select name="table_type" value={form.table_type} onChange={handleChange}>
            <option value="rate">SC Rate Table</option>
            <option value="flat">SC Flat Rate Table</option>
          </select>
        </div>
        <div className="form-field">
          <label>Position name (optional)</label>
          <input name="position_name" value={form.position_name} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Description (optional)</label>
          <input name="description" value={form.description} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Pay period (optional)</label>
          <select name="pay_period_type" value={form.pay_period_type} onChange={handleChange}>
            <option>Monthly</option>
            <option>Quarterly</option>
            <option>Annual</option>
          </select>
        </div>
        <div className="form-field">
          <label>Title (optional)</label>
          <input name="title" value={form.title} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Business group (optional)</label>
          <input name="business_group" value={form.business_group} onChange={handleChange} />
        </div>
      </div>

      <div className="form-actions">
        <button type="button" className="btn-primary" onClick={savePlan} disabled={loading}>
          {loading ? "Saving…" : "Save plan"}
        </button>
      </div>
    </div>
  );
}

export default PlanHeaderForm;
