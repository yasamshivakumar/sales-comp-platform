import { Link } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import PlanHeaderForm, { commissionTableLabel } from "./PlanHeaderForm";
import TierForm from "./TierForm";
import TierList from "./TierList";
import LookupTierForm from "./LookupTierForm";
import LookupTierList from "./LookupTierList";
import PlanVersionHistory, { VersionBadge } from "./PlanVersionHistory";
import { BUSINESS_GROUP_OPTIONS } from "../utils/businessGroups";
import "./compPlans.css";

function formatPlanMonth(plan) {
  const start = plan?.effective_start_date;
  if (!start) return "—";
  const [year, month] = start.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function planRateCount(plan) {
  return (
    (plan.sc_rate_tables?.length || 0) +
    (plan.sc_flat_rate_tables?.length || 0) +
    (plan.sc_lookup_tables?.length || 0)
  );
}

function planStatusClass(status) {
  const s = String(status || "").toLowerCase();
  if (s === "active") return "cp-plan-status--active";
  if (s === "draft") return "cp-plan-status--draft";
  return "cp-plan-status--inactive";
}

function computePlanKpis(plans) {
  const total = plans.length;
  let publishedDisplay = 0;
  let draftPending = 0;
  let missingRates = 0;
  for (const plan of plans) {
    const cv = plan.current_version;
    if (cv?.status === "Published") publishedDisplay += 1;
    if (cv?.status === "Draft") draftPending += 1;
    if (planRateCount(plan) === 0) missingRates += 1;
  }
  return { total, publishedDisplay, draftPending, missingRates };
}

function AiPlanBuilder({ onPlanCreated, onCancel }) {
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
      onPlanCreated?.(res.data.plan);
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
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={loading}>
          Back to plans list
        </button>
      </div>
      <p className="ai-plan-builder__hint">
        Describe the compensation logic. Incentra creates one plan with Version 1 covering
        your effective date range (not one plan per month).
      </p>

      <div className="form-grid">
        <div className="form-field form-field--wide">
          <label>Plan request *</label>
          <textarea
            name="prompt"
            value={form.prompt}
            onChange={handleChange}
            rows={4}
            placeholder="Example: Build a USA Sales Rep plan with 5% up to $50k, 7% up to $100k, and 10% above $100k. Add a $500 bonus for enterprise product deals."
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
          <small style={{ color: "var(--text-muted)", fontSize: 12 }}>
            Optional. Leave blank for open-ended.
          </small>
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

  const kpis = computePlanKpis(plans);

  return (
    <div className="cp-module">
      <PageHeader badge="Configuration" title="Compensation Plans" />

      <div className="cp-toolbar">
        <div className="cp-toolbar__text">
          <p className="cp-toolbar__title">Plan library</p>
          <p className="cp-toolbar__hint">
            One plan per role/position. Versions hold rates and effective dates.
            Quotas are monthly rows on a version — not a new plan every month.
          </p>
        </div>
        <div className="cp-toolbar__actions">
        {view === "list" ? (
          <>
            <button
              type="button"
              className="cp-btn-ghost"
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
            <p className="cp-loading">Loading plans…</p>
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
            <>
            <div className="cp-kpis">
              <article className="cp-kpi">
                <span className="cp-kpi__label">Total plans</span>
                <span className="cp-kpi__value">{kpis.total}</span>
              </article>
              <article className="cp-kpi cp-kpi--success">
                <span className="cp-kpi__label">Published (current)</span>
                <span className="cp-kpi__value">{kpis.publishedDisplay}</span>
              </article>
              <article className="cp-kpi cp-kpi--warning">
                <span className="cp-kpi__label">Draft pending</span>
                <span className="cp-kpi__value">{kpis.draftPending}</span>
              </article>
              <article className="cp-kpi cp-kpi--teal">
                <span className="cp-kpi__label">Missing rates</span>
                <span className="cp-kpi__value">{kpis.missingRates}</span>
              </article>
            </div>
            <div className="cp-table-card">
            <div className="comp-plans-table-wrap">
              <table className="comp-plans-table enterprise-table">
                <thead>
                  <tr>
                    <th>Plan name</th>
                    <th>Version</th>
                    <th>Effective</th>
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
                    const rateCount = planRateCount(plan);
                    const ruleCount = plan.commission_rules?.length || 0;
                    const isSelected = selectedPlan?.id === plan.id;
                    return (
                      <tr
                        key={plan.id}
                        className={isSelected ? "cp-row--selected" : undefined}
                      >
                        <td>
                          <span className="cp-plan-cell__name">{plan.plan_name}</span>
                          <span className="cp-plan-cell__meta">{plan.role || "No role"}</span>
                        </td>
                        <td>
                          {plan.current_version ? (
                            <>
                              <span className="cp-version-tag">
                                v{plan.current_version.version_number}
                              </span>
                              <VersionBadge status={plan.current_version.status} />
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          {plan.current_version
                            ? `${plan.current_version.effective_from || "—"} → ${
                                plan.current_version.effective_to || "open"
                              }`
                            : formatPlanMonth(plan)}
                        </td>
                        <td>{plan.role || "—"}</td>
                        <td>{plan.position_name || "—"}</td>
                        <td>
                          <span
                            className={`cp-plan-status ${planStatusClass(plan.status)}`}
                          >
                            {plan.status}
                          </span>
                        </td>
                        <td>{commissionTableLabel(plan.commission_table_type)}</td>
                        <td>{rateCount}</td>
                        <td>{ruleCount}</td>
                        <td>
                          <div className="comp-plans-actions">
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={() => handleEditPlan(plan)}
                              disabled={
                                plan.current_version &&
                                !plan.current_version.is_editable
                              }
                              title={
                                plan.current_version &&
                                !plan.current_version.is_editable
                                  ? "Published versions are read-only. Clone a version to edit."
                                  : "Edit plan details"
                              }
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
            </div>
            </>
          )}

          {selectedPlan && (
            <div className="comp-plans-manage">
              <h2 className="cp-manage__title panel__title">
                Commission rates — {selectedPlan.plan_name}
                {selectedPlan.current_version ? (
                  <>
                    {" "}
                    <VersionBadge status={selectedPlan.current_version.status} />{" "}
                    <span className="muted-mini">
                      v{selectedPlan.current_version.version_number}
                    </span>
                  </>
                ) : (
                  <> ({formatPlanMonth(selectedPlan)})</>
                )}
              </h2>
              {selectedPlan.current_version &&
              !selectedPlan.current_version.is_editable ? (
                <p className="plan-readonly-banner">
                  This version is {selectedPlan.current_version.status} and read-only.
                  Use <strong>Clone</strong> in Version history below to create an editable
                  draft, then publish when ready.
                </p>
              ) : null}
              {selectedPlan.commission_table_type === "HIGHEST" ? (
                <p className="plan-readonly-banner">
                  Highest Rate Table: monthly successful sales are summed first, then the
                  matching tier’s rate applies to the <strong>full monthly total</strong>.
                </p>
              ) : null}
              {selectedPlan.commission_table_type === "MARGINAL" ? (
                <p className="plan-readonly-banner">
                  Marginal Rate Table: bands fill up across the month’s orders. Each order first
                  <strong> tops up the current band’s leftover</strong> at its rate, then the rest of
                  that order is paid at the next band’s rate. The top band is open-ended.
                </p>
              ) : null}
              <div className="cp-manage__grid">
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
              <div className="cp-manage__rules">
                <Link
                  to={`/commission-rules?plan=${selectedPlan.id}`}
                  className="btn-secondary"
                >
                  Manage commission rules →
                </Link>
                <p className="cp-manage__rules-hint">
                  Rules run after rate tables: conditions filter orders, results apply bonuses,
                  overrides, holds, and earning classification.
                </p>
              </div>
              <PlanVersionHistory
                plan={selectedPlan}
                onVersionsChanged={() => refreshSelectedPlan(selectedPlan.id)}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default CompensationPlans;
