import { Link } from "react-router-dom";

function CompPlansHealthDashboard({ summary, loading, onFilterHealth }) {
  const healthy = summary?.healthy_plans ?? 0;
  const warning = summary?.warning_plans ?? 0;
  const critical = summary?.critical_plans ?? 0;
  const attention = summary?.attention_plans || [];
  const total = Math.max(1, healthy + warning + critical);

  return (
    <section className="cp-health-dash panel" aria-label="Plan health dashboard">
      <div className="cp-section-head">
        <div>
          <h2 className="cp-section-title">Plan health dashboard</h2>
          <p className="cp-section-hint">
            Compensation readiness across configuration, coverage, and versions
          </p>
        </div>
      </div>

      <div className="cp-health-dash__stats">
        <button
          type="button"
          className="cp-health-stat cp-health-stat--healthy"
          onClick={() => onFilterHealth?.("healthy")}
        >
          <span className="cp-health-stat__label">Healthy</span>
          <span className="cp-health-stat__value">{loading ? "—" : healthy}</span>
          <span className="cp-health-stat__bar" style={{ width: `${(healthy / total) * 100}%` }} />
        </button>
        <button
          type="button"
          className="cp-health-stat cp-health-stat--warning"
          onClick={() => onFilterHealth?.("warning")}
        >
          <span className="cp-health-stat__label">Review Required</span>
          <span className="cp-health-stat__value">{loading ? "—" : warning}</span>
          <span className="cp-health-stat__bar" style={{ width: `${(warning / total) * 100}%` }} />
        </button>
        <button
          type="button"
          className="cp-health-stat cp-health-stat--critical"
          onClick={() => onFilterHealth?.("critical")}
        >
          <span className="cp-health-stat__label">Critical Attention</span>
          <span className="cp-health-stat__value">{loading ? "—" : critical}</span>
          <span className="cp-health-stat__bar" style={{ width: `${(critical / total) * 100}%` }} />
        </button>
      </div>

      <div className="cp-health-dash__list">
        <h3 className="cp-mini-chart__title">Plans requiring action</h3>
        {loading && !attention.length ? (
          <p className="cp-tab-lead">Loading health insights…</p>
        ) : attention.length === 0 ? (
          <div className="cp-empty-inline">
            <p>All plans look healthy</p>
            <p className="cp-tab-lead">No configuration blockers detected.</p>
          </div>
        ) : (
          <ul className="cp-attention-list">
            {attention.map((row) => (
              <li key={row.id} className={`cp-attention-item cp-attention-item--${row.level}`}>
                <div className="cp-attention-item__main">
                  <Link to={`/comp-plans/${row.id}/overview`} className="cp-attention-item__name">
                    {row.plan_name}
                  </Link>
                  <span className={`cp-health cp-health--${row.level}`}>
                    <strong>{row.score}%</strong> {row.status}
                  </span>
                </div>
                {row.issues?.length ? (
                  <ul className="cp-attention-item__issues">
                    {row.issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                ) : null}
                <div className="cp-attention-item__actions">
                  <Link className="btn-secondary" to={`/comp-plans/${row.id}/overview`}>
                    Open Workspace
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default CompPlansHealthDashboard;
