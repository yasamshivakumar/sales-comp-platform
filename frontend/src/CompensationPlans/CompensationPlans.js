import { Link } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import PlanHeaderForm from "./PlanHeaderForm";
import TierForm from "./TierForm";
import TierList from "./TierList";
import LookupTierForm from "./LookupTierForm";
import LookupTierList from "./LookupTierList";
import MonthPickerField from "../Components/MonthPickerField";
import { BUSINESS_GROUP_OPTIONS } from "../utils/businessGroups";
import "./compPlans.css";

function formatPlanMonth(plan) {
  const start = plan?.effective_start_date;
  if (!start) return "—";
  const [year, month] = start.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function monthStart(month) {
  return month ? `${month}-01` : "";
}

function monthEnd(month) {
  if (!month) return "";
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(year, monthNumber, 0).getDate();
  return `${month}-${String(lastDay).padStart(2, "0")}`;
}

function AiPlanBuilder({ onPlanCreated, onCancel }) {
  const { success, error } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState({
    prompt: "",
    role: "Sales Rep",
    business_group: "USA",
    comp_period: "",
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
    if (!form.comp_period) {
      error("Compensation month is required.");
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
        effective_start_date: monthStart(form.comp_period),
        effective_end_date: monthEnd(form.comp_period),
        commission_table_type: form.commission_table_type,
        position_name: form.position_name.trim(),
        sample_orders: sampleOrders,
      };
      const res = await api.post("ai/compensation-plan-builder/", payload);
      setResult(res.data);
      onPlanCreated?.(res.data.plan);
      success("AI compensation plan created and validated.");
    } catch (err) {
      error(getApiErrorMessage(err, "AI plan builder failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel ai-plan-builder">
      <div className="ai-plan-builder__head">
        <div>
          <p className="ai-plan-builder__eyebrow">Production AI</p>
          <h2 className="panel__title">AI Compensation Plan Builder</h2>
        </div>
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={loading}>
          Back to plans list
        </button>
      </div>
      <p className="ai-plan-builder__hint">
        Describe the compensation logic. Incentra validates the AI JSON, simulates sample orders,
        creates the plan/rules, and records an audit log.
      </p>

      <div className="form-grid">
        <div className="form-field form-field--wide">
          <label>Plan request *</label>
          <textarea
            name="prompt"
            value={form.prompt}
            onChange={handleChange}
            rows={4}
            placeholder="Example: Build a monthly USA Sales Rep plan with 5% up to $50k, 7% up to $100k, and 10% above $100k. Add a $500 bonus for enterprise product deals."
          />
        </div>
        <div className="form-field">
          <label>Role *</label>
          <input name="role" value={form.role} onChange={handleChange} />
        </div>
        <div className="form-field">
          <MonthPickerField
            label="Compensation month *"
            value={form.comp_period}
            onChange={(value) => setForm({ ...form, comp_period: value })}
            disabled={loading}
            required
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
            <option value="RATE">Rate tiers</option>
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
      </div>

      {result && (
        <div className="ai-plan-builder__result">
          <strong>{result.plan?.plan_name}</strong> created with {result.rules_created?.length || 0} rule(s).
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

function CompensationPlans() {
  const [plans, setPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [editingPlan, setEditingPlan] = useState(null);
  const [editingTier, setEditingTier] = useState(null);
  const [view, setView] = useState("list");
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  const fetchPlans = useCallback(() => {
    setLoading(true);
    api
      .get("compensation-plans/")
      .then((res) => setPlans(res.data))
      .catch(() => error("Failed to load compensation plans"))
      .finally(() => setLoading(false));
  }, [error]);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const refreshSelectedPlan = useCallback(async (planId) => {
    if (!planId) return;
    try {
      const res = await api.get(`compensation-plans/${planId}/`);
      setSelectedPlan(res.data);
      setPlans((prev) =>
        prev.map((p) => (p.id === res.data.id ? res.data : p))
      );
    } catch {
      error("Failed to refresh plan details");
    }
  }, [error]);

  const handlePlanCreated = (plan) => {
    fetchPlans();
    setSelectedPlan(plan);
    setEditingTier(null);
    setView("list");
    success("Compensation plan created. Add commission rate tiers below if needed.");
  };

  const handlePlanUpdated = (plan) => {
    setPlans((prev) => prev.map((p) => (p.id === plan.id ? plan : p)));
    setSelectedPlan(plan);
    setEditingPlan(null);
    setEditingTier(null);
    setView("list");
    success("Compensation plan updated.");
  };

  const handleTierUpdated = () => {
    if (selectedPlan?.id) {
      refreshSelectedPlan(selectedPlan.id);
    } else {
      fetchPlans();
    }
    setEditingTier(null);
    success("Commission rates saved.");
  };

  const handleManagePlan = (plan) => {
    setSelectedPlan(plan);
    setEditingTier(null);
    refreshSelectedPlan(plan.id);
  };

  const handleEditPlan = async (plan) => {
    try {
      const res = await api.get(`compensation-plans/${plan.id}/`);
      setEditingPlan(res.data);
      setEditingTier(null);
      setView("edit");
    } catch {
      error("Failed to load plan details for editing");
    }
  };

  const gridStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "24px",
    marginBottom: "24px",
  };

  return (
    <div>
      <PageHeader badge="Configuration" title="Compensation Plans" />

      <div className="comp-plans-toolbar">
        <p className="comp-plans-toolbar__hint">
          Each plan applies to one calendar month. Create a new plan per month and role/position.
        </p>
        {view === "list" ? (
          <>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setView("ai")}
            >
              AI Plan Builder
            </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setView("create")}
          >
            + New compensation plan
          </button>
          </>
        ) : (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              setEditingPlan(null);
              setEditingTier(null);
              setView("list");
            }}
          >
            ← Back to plans list
          </button>
        )}
      </div>

      {view === "create" && (
        <PlanHeaderForm
          onPlanCreated={handlePlanCreated}
          onCancel={() => setView("list")}
        />
      )}

      {view === "edit" && editingPlan && (
        <PlanHeaderForm
          initialPlan={editingPlan}
          onPlanUpdated={handlePlanUpdated}
          onCancel={() => {
            setEditingPlan(null);
            setEditingTier(null);
            setView("list");
          }}
        />
      )}

      {view === "ai" && (
        <AiPlanBuilder
          onPlanCreated={handlePlanCreated}
          onCancel={() => setView("list")}
        />
      )}

      {view === "list" && (
        <>
          {loading && plans.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>Loading plans…</p>
          ) : plans.length === 0 ? (
            <div className="comp-plans-empty">
              <p>No compensation plans yet.</p>
              <button
                type="button"
                className="btn-primary"
                onClick={() => setView("create")}
              >
                Create your first plan
              </button>
            </div>
          ) : (
            <div className="comp-plans-table-wrap panel" style={{ padding: 0 }}>
              <table className="comp-plans-table enterprise-table">
                <thead>
                  <tr>
                    <th>Plan name</th>
                    <th>Month</th>
                    <th>Role</th>
                    <th>Position</th>
                    <th>Status</th>
                    <th>Table</th>
                    <th>Rates</th>
                    <th>Rules</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {plans.map((plan) => {
                    const rateCount =
                      (plan.sc_rate_tables?.length || 0) +
                      (plan.sc_flat_rate_tables?.length || 0) +
                      (plan.sc_lookup_tables?.length || 0);
                    const ruleCount = plan.commission_rules?.length || 0;
                    const isSelected = selectedPlan?.id === plan.id;
                    return (
                      <tr
                        key={plan.id}
                        style={
                          isSelected
                            ? { background: "rgba(99, 102, 241, 0.1)" }
                            : undefined
                        }
                      >
                        <td>
                          <strong>{plan.plan_name}</strong>
                        </td>
                        <td>{formatPlanMonth(plan)}</td>
                        <td>{plan.role || "—"}</td>
                        <td>{plan.position_name || "—"}</td>
                        <td>{plan.status}</td>
                        <td>{plan.commission_table_type || "—"}</td>
                        <td>{rateCount}</td>
                        <td>{ruleCount}</td>
                        <td>
                          <div className="comp-plans-actions">
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={() => handleEditPlan(plan)}
                            >
                              Edit details
                            </button>
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={() => handleManagePlan(plan)}
                            >
                              {isSelected ? "Managing" : "Manage rates"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {selectedPlan && (
            <div className="comp-plans-manage">
              <h2 className="panel__title" style={{ marginBottom: 16 }}>
                Commission rates — {selectedPlan.plan_name} ({formatPlanMonth(selectedPlan)})
              </h2>
              <div style={gridStyle}>
                {selectedPlan.commission_table_type === "LOOKUP" ? (
                  <>
                    <LookupTierForm
                      selectedPlan={selectedPlan}
                      editingTier={editingTier}
                      onTierUpdated={handleTierUpdated}
                      onCancelEdit={() => setEditingTier(null)}
                    />
                    <LookupTierList
                      selectedPlan={selectedPlan}
                      onEditTier={(row, index) => setEditingTier({ row, index, type: "lookup" })}
                    />
                  </>
                ) : (
                  <>
                    <TierForm
                      selectedPlan={selectedPlan}
                      editingTier={editingTier}
                      onTierUpdated={handleTierUpdated}
                      onCancelEdit={() => setEditingTier(null)}
                    />
                    <TierList
                      selectedPlan={selectedPlan}
                      onEditTier={(row, index) => setEditingTier({ row, index, type: "rate" })}
                    />
                  </>
                )}
              </div>
              <div style={{ marginTop: 16 }}>
                <Link
                  to={`/commission-rules?plan=${selectedPlan.id}`}
                  className="btn-secondary"
                >
                  Manage commission rules →
                </Link>
                <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>
                  Rules run after rate tables: conditions filter orders, results apply bonuses,
                  overrides, holds, and earning classification.
                </p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default CompensationPlans;
