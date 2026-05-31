import { useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";

function TierForm({ selectedPlan, onTierCreated }) {
  const { success, error } = useToast();
  const [loading, setLoading] = useState(false);

  const [form, setForm] = useState({
    tier_name: "",
    min_sales: "",
    max_sales: "",
    commission_percent: "",
    bonus_amount: "0",
    is_active: true,
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const saveTier = async () => {
    if (!form.tier_name.trim()) {
      error("Tier name is required");
      return;
    }

    setLoading(true);
    try {
      await api.post("compensation-tiers/", {
        ...form,
        plan: selectedPlan.id,
      });

      success("Tier created successfully!");

      setForm({
        tier_name: "",
        min_sales: "",
        max_sales: "",
        commission_percent: "",
        bonus_amount: "0",
        is_active: true,
      });

      onTierCreated();
    } catch (err) {
      error(err.response?.data?.message || "Error creating tier");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3 className="panel__title">Add tier: {selectedPlan.plan_name}</h3>

      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="tier_name">Tier name</label>
          <input
            id="tier_name"
            name="tier_name"
            value={form.tier_name}
            onChange={handleChange}
            placeholder="Tier name"
          />
        </div>
        <div className="form-field">
          <label htmlFor="min_sales">Min sales</label>
          <input
            id="min_sales"
            type="number"
            name="min_sales"
            value={form.min_sales}
            onChange={handleChange}
            placeholder="Min sales"
          />
        </div>
        <div className="form-field">
          <label htmlFor="max_sales">Max sales</label>
          <input
            id="max_sales"
            type="number"
            name="max_sales"
            value={form.max_sales}
            onChange={handleChange}
            placeholder="Max sales"
          />
        </div>
        <div className="form-field">
          <label htmlFor="commission_percent">Commission %</label>
          <input
            id="commission_percent"
            type="number"
            name="commission_percent"
            value={form.commission_percent}
            onChange={handleChange}
            placeholder="Commission %"
          />
        </div>
        <div className="form-field">
          <label htmlFor="bonus_amount">Bonus amount</label>
          <input
            id="bonus_amount"
            type="number"
            name="bonus_amount"
            value={form.bonus_amount}
            onChange={handleChange}
            placeholder="Bonus amount"
          />
        </div>
        <div className="checkbox-field">
          <input
            type="checkbox"
            id="tier_is_active"
            name="is_active"
            checked={form.is_active}
            onChange={handleChange}
          />
          <label htmlFor="tier_is_active">Active</label>
        </div>
      </div>

      <div className="form-actions">
        <button
          type="button"
          className="btn-success"
          onClick={saveTier}
          disabled={loading}
        >
          {loading ? "Creating…" : "Save tier"}
        </button>
      </div>
    </div>
  );
}

export default TierForm;
