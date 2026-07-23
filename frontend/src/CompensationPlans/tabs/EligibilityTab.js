import { Link, useOutletContext } from "react-router-dom";

function EligibilityTab() {
  const { plan } = useOutletContext();
  const summary = plan.business_summary || {};
  const coverage = plan.coverage || {};
  const hasPosition = Boolean((plan.position_name || "").trim());
  const hasRole = Boolean((plan.role || "").trim());
  const configured = hasPosition || hasRole;

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <h2 className="panel__title">Eligibility</h2>
        <p className="cp-tab-lead">
          Participants are matched the same way commission calculation assigns plans:
          position name first, then role.
        </p>

        <div className={`cp-component-card${configured ? " cp-component-card--ok" : ""}`}>
          <h3>{configured ? "Configured" : "Not Configured"}</h3>
          <p className="cp-tab-lead">{summary.who_receives || "No eligibility criteria."}</p>
        </div>

        <div className="cp-overview-grid" style={{ marginTop: 16 }}>
          <div>
            <span className="cp-card__label">Match method</span>
            <span className="cp-card__value">
              {hasPosition ? "Position name" : hasRole ? "Role" : "—"}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Position</span>
            <span className="cp-card__value">{plan.position_name || "—"}</span>
          </div>
          <div>
            <span className="cp-card__label">Role</span>
            <span className="cp-card__value">{plan.role || "—"}</span>
          </div>
          <div>
            <span className="cp-card__label">Business unit</span>
            <span className="cp-card__value">{plan.business_group || "—"}</span>
          </div>
          <div>
            <span className="cp-card__label">Departments in coverage</span>
            <span className="cp-card__value">
              {(coverage.departments || []).join(", ") || "—"}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Regions in coverage</span>
            <span className="cp-card__value">
              {(coverage.regions || []).join(", ") || "—"}
            </span>
          </div>
        </div>

        <div className="cp-card__actions" style={{ marginTop: 16 }}>
          <Link className="btn-primary" to={`/comp-plans/${plan.id}/participants`}>
            View participants
          </Link>
          <Link className="btn-secondary" to={`/comp-plans/${plan.id}/settings`}>
            Edit eligibility in Settings
          </Link>
        </div>
      </section>
    </div>
  );
}

export default EligibilityTab;
