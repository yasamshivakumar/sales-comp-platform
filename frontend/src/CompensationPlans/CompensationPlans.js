import { Link } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import PlanHeaderForm from "./PlanHeaderForm";
import TierForm from "./TierForm";
import TierList from "./TierList";
import LookupTierForm from "./LookupTierForm";
import LookupTierList from "./LookupTierList";
import "./compPlans.css";

function formatPlanMonth(plan) {
  const start = plan?.effective_start_date;
  if (!start) return "—";
  const [year, month] = start.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function CompensationPlans() {
  const [plans, setPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
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
    setView("list");
    success("Compensation plan created. Add commission rate tiers below if needed.");
  };

  const handleTierUpdated = () => {
    if (selectedPlan?.id) {
      refreshSelectedPlan(selectedPlan.id);
    } else {
      fetchPlans();
    }
    success("Commission rates saved.");
  };

  const handleManagePlan = (plan) => {
    setSelectedPlan(plan);
    refreshSelectedPlan(plan.id);
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
          <button
            type="button"
            className="btn-primary"
            onClick={() => setView("create")}
          >
            + New compensation plan
          </button>
        ) : (
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setView("list")}
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
                          <button
                            type="button"
                            className="btn-secondary"
                            style={{ padding: "6px 12px", fontSize: 13 }}
                            onClick={() => handleManagePlan(plan)}
                          >
                            {isSelected ? "Managing" : "Manage rates"}
                          </button>
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
                      onTierUpdated={handleTierUpdated}
                    />
                    <LookupTierList selectedPlan={selectedPlan} />
                  </>
                ) : (
                  <>
                    <TierForm
                      selectedPlan={selectedPlan}
                      onTierUpdated={handleTierUpdated}
                    />
                    <TierList selectedPlan={selectedPlan} />
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
