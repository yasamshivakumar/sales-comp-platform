import { useNavigate, useOutletContext } from "react-router-dom";
import PlanHeaderForm from "../PlanHeaderForm";

function SettingsTab() {
  const navigate = useNavigate();
  const { plan, reloadPlan } = useOutletContext();
  const editable = !plan.current_version || plan.current_version.is_editable;

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel cp-form-card">
        <h2 className="panel__title">Plan settings</h2>
        {!editable && (
          <p className="cp-tab-lead plan-readonly-banner">
            Published versions are read-only for calculation fields. Clone a version from
            the Versions tab to edit rates and effective logic. You can still update the
            plan name and description where the API allows.
          </p>
        )}
        <PlanHeaderForm
          initialPlan={plan}
          onPlanUpdated={async (updated) => {
            await reloadPlan();
            navigate(`/comp-plans/${updated.id}/overview`);
          }}
          onCancel={() => navigate(`/comp-plans/${plan.id}/overview`)}
        />
      </section>
    </div>
  );
}

export default SettingsTab;
