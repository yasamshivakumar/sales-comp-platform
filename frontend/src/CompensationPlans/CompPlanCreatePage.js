import { useNavigate } from "react-router-dom";
import PlanHeaderForm from "./PlanHeaderForm";

function CompPlanCreatePage() {
  const navigate = useNavigate();

  return (
    <div className="cp-module">
      <div className="panel cp-form-card">
        <h2 className="panel__title">New compensation plan</h2>
        <PlanHeaderForm
          onPlanCreated={(plan) => navigate(`/comp-plans/${plan.id}/rates`)}
          onCancel={() => navigate("/comp-plans")}
        />
      </div>
    </div>
  );
}

export default CompPlanCreatePage;
