import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import PlanHeaderForm from "./PlanHeaderForm";
import TierForm from "./TierForm";
import TierList from "./TierList";

function CompensationPlans() {
  const [plans, setPlans] = useState([]);
  const [tiers, setTiers] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const { success, error } = useToast();

  useEffect(() => {
    fetchPlans();
    fetchTiers();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchPlans = () => {
    api
      .get("compensation-plans/")
      .then((res) => setPlans(res.data))
      .catch(() => {
        error("Failed to load compensation plans");
      });
  };

  const fetchTiers = () => {
    api
      .get("compensation-tiers/")
      .then((res) => setTiers(res.data))
      .catch(() => {
        error("Failed to load tiers");
      });
  };

  const handlePlanCreated = (plan) => {
    setSelectedPlan(plan);
    fetchPlans();
    success("Compensation plan created successfully!");
  };

  const handleTierCreated = () => {
    fetchTiers();
    fetchPlans();
    success("Tier created successfully!");
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

      <PlanHeaderForm onPlanCreated={handlePlanCreated} />

      {plans.length > 0 && (
        <div className="card" style={{ padding: "20px", marginBottom: "24px" }}>
          <label
            htmlFor="plan-select"
            style={{ display: "block", marginBottom: "8px", fontWeight: 600 }}
          >
            Select plan to manage tiers
          </label>
          <select
            id="plan-select"
            className="input"
            value={selectedPlan?.id ?? ""}
            onChange={(e) => {
              const plan = plans.find((p) => String(p.id) === e.target.value);
              setSelectedPlan(plan || null);
            }}
          >
            <option value="">— Choose a plan —</option>
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.plan_name} ({plan.role || "no role"})
              </option>
            ))}
          </select>
        </div>
      )}

      {selectedPlan && (
        <div style={gridStyle}>
          <TierForm
            selectedPlan={selectedPlan}
            onTierCreated={handleTierCreated}
          />

          <TierList
            tiers={tiers.filter((tier) => tier.plan === selectedPlan.id)}
          />
        </div>
      )}
    </div>
  );
}

export default CompensationPlans;
