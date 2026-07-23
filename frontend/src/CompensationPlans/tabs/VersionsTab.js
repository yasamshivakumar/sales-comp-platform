import { useOutletContext } from "react-router-dom";
import PlanVersionHistory from "../PlanVersionHistory";

function VersionsTab() {
  const { plan, reloadPlan } = useOutletContext();

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <h2 className="panel__title">Version timeline</h2>
        <p className="cp-tab-lead">
          Lifecycle: Draft → Published → Archived. Clone a published version to edit.
          Compare any two versions side by side.
        </p>
        <ol className="cp-flow cp-flow--inline" aria-label="Version lifecycle">
          <li className="cp-flow__step cp-flow__step--done">
            <span className="cp-flow__dot" />
            <div>
              <strong>Draft</strong>
              <p className="cp-tab-lead">Editable configuration</p>
            </div>
          </li>
          <li className="cp-flow__step cp-flow__step--done">
            <span className="cp-flow__dot" />
            <div>
              <strong>Published</strong>
              <p className="cp-tab-lead">Live for calculation</p>
            </div>
          </li>
          <li className="cp-flow__step">
            <span className="cp-flow__dot" />
            <div>
              <strong>Archived</strong>
              <p className="cp-tab-lead">Retired from active use</p>
            </div>
          </li>
        </ol>
        <div className="cp-versions-timeline-wrap">
          <PlanVersionHistory plan={plan} onVersionsChanged={() => reloadPlan()} />
        </div>
      </section>
    </div>
  );
}

export default VersionsTab;
