import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import { BUSINESS_GROUP_OPTIONS } from "../utils/businessGroups";
import { AI_PLAN_EXAMPLES } from "./compPlanUtils";

function AiPlanBuilder() {
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    prompt: "",
    role: "Sales Rep",
    business_group: "USA",
    effective_from: "",
    effective_to: "",
    commission_table_type: "RATE",
    position_name: "",
    sample_orders: "25000, 75000, 150000",
  });

  const handleChange = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value });
  };

  const createWithAi = async () => {
    if (!form.prompt.trim()) {
      error("Describe the plan you want AI to build.");
      return;
    }
    if (!form.effective_from) {
      error("Effective from date is required.");
      return;
    }
    if (form.effective_to && form.effective_to < form.effective_from) {
      error("Effective to cannot be before effective from.");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const sampleOrders = form.sample_orders
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
        .map((sales_amount) => ({ sales_amount }));
      const payload = {
        prompt: form.prompt.trim(),
        role: form.role.trim() || "Sales Rep",
        business_group: form.business_group,
        effective_start_date: form.effective_from,
        effective_end_date: form.effective_to || null,
        commission_table_type: form.commission_table_type,
        position_name: form.position_name.trim(),
        sample_orders: sampleOrders,
      };
      const res = await api.post("ai/compensation-plan-builder/", payload);
      setResult(res.data);
      success("AI compensation plan created and validated.");
    } catch (err) {
      error(getApiErrorMessage(err, "AI plan builder failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel ai-plan-builder cp-form-card">
      <div className="ai-plan-builder__head">
        <div>
          <p className="ai-plan-builder__eyebrow">Production AI</p>
          <h2 className="panel__title">AI Compensation Plan Builder</h2>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => navigate("/comp-plans")}
          disabled={loading}
        >
          Back to catalog
        </button>
      </div>
      <p className="ai-plan-builder__hint">
        Describe the compensation logic. Incentra creates one plan with Version 1 covering
        your effective date range.
      </p>

      <div className="ai-plan-builder__examples" aria-label="Example prompts">
        <p className="ai-plan-builder__examples-label">Try an example</p>
        <div className="ai-plan-builder__examples-list">
          {AI_PLAN_EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="ai-plan-builder__example"
              disabled={loading}
              onClick={() => setForm((current) => ({ ...current, prompt: example }))}
            >
              {example}
            </button>
          ))}
        </div>
      </div>

      <div className="form-grid">
        <div className="form-field form-field--wide">
          <label>Plan request *</label>
          <textarea
            name="prompt"
            value={form.prompt}
            onChange={handleChange}
            rows={4}
            placeholder='Example: "Sales reps receive 5% until 100K then 7%."'
          />
        </div>
        <div className="form-field">
          <label>Role *</label>
          <input name="role" value={form.role} onChange={handleChange} />
        </div>
        <div className="form-field">
          <label>Effective from *</label>
          <input
            type="date"
            name="effective_from"
            value={form.effective_from}
            onChange={handleChange}
            disabled={loading}
            required
          />
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
        </div>
        <div className="form-field">
          <label>Business group</label>
          <select name="business_group" value={form.business_group} onChange={handleChange}>
            {BUSINESS_GROUP_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} ({option.currency})
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label>Commission table</label>
          <select
            name="commission_table_type"
            value={form.commission_table_type}
            onChange={handleChange}
          >
            <option value="RATE">Rate tiers (per order)</option>
            <option value="HIGHEST">Highest rate (monthly total)</option>
            <option value="MARGINAL">Marginal rate (bands fill)</option>
            <option value="FLAT">Flat rate</option>
            <option value="LOOKUP">Lookup table</option>
          </select>
        </div>
        <div className="form-field">
          <label>Position name</label>
          <input
            name="position_name"
            value={form.position_name}
            onChange={handleChange}
            placeholder="Optional"
          />
        </div>
        <div className="form-field">
          <label>Sample order amounts</label>
          <input name="sample_orders" value={form.sample_orders} onChange={handleChange} />
        </div>
      </div>

      <div className="form-actions">
        <button type="button" className="btn-primary" onClick={createWithAi} disabled={loading}>
          {loading ? "Building with AI..." : "Build and create plan"}
        </button>
        {result?.plan?.id && (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate(`/comp-plans/${result.plan.id}/overview`)}
          >
            Open plan workspace
          </button>
        )}
      </div>

      {result && (
        <div className="ai-plan-builder__result">
          <strong>{result.plan?.plan_name}</strong> created with{" "}
          {result.rules_created?.length || 0} rule(s).
          {result.simulation?.length > 0 && (
            <ul>
              {result.simulation.map((row, index) => (
                <li key={index}>
                  Sample {row.sales_amount}: estimated commission {row.estimated_commission}
                </li>
              ))}
            </ul>
          )}
          {result.warnings?.length > 0 && (
            <p>Review warning: {result.warnings.join(" ")}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default AiPlanBuilder;
