import { Link, useOutletContext } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../../api";
import { useToast } from "../../Components/Toast";
import { VersionBadge } from "../PlanVersionHistory";
import {
  calculationMethodLabel,
  displayVersionLabel,
  formatCoverageList,
  formatEffectiveRange,
  formatMoney,
} from "../compPlanUtils";

function MiniBarChart({ title, items, ariaLabel }) {
  const rows = items || [];
  const max = Math.max(1, ...rows.map((r) => Number(r.count || r.projected || 0)));
  return (
    <div className="cp-mini-chart" aria-label={ariaLabel || title}>
      <h3 className="cp-mini-chart__title">{title}</h3>
      {rows.length === 0 ? (
        <p className="cp-tab-lead">No data yet</p>
      ) : (
        <ul className="cp-mini-chart__list">
          {rows.map((row) => {
            const value = Number(row.count ?? row.projected ?? 0);
            const label = row.label || row.name || `M+${row.month_offset ?? 0}`;
            const pct = Math.round((value / max) * 100);
            return (
              <li key={label} className="cp-mini-chart__row">
                <span className="cp-mini-chart__label">{label}</span>
                <span className="cp-mini-chart__track" aria-hidden="true">
                  <span className="cp-mini-chart__fill" style={{ width: `${pct}%` }} />
                </span>
                <span className="cp-mini-chart__value">{value.toLocaleString()}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function OverviewTab() {
  const { plan } = useOutletContext();
  const { error } = useToast();
  const cv = plan.current_version;
  const summary = plan.business_summary || {};
  const coverage = plan.coverage || {};
  const health = plan.health || {};
  const configHealth = plan.configuration_health || {};
  const actions = plan.actions || [];
  const [activity, setActivity] = useState([]);
  const [insights, setInsights] = useState(null);

  const loadExtras = useCallback(async () => {
    if (!plan?.id) return;
    try {
      const [actRes, insightRes] = await Promise.all([
        api.get(`compensation-plans/${plan.id}/activity/?limit=12`),
        api.get(`compensation-plans/${plan.id}/insights/`),
      ]);
      setActivity(actRes.data?.results || []);
      setInsights(insightRes.data || null);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load plan insights"));
    }
  }, [plan?.id, error]);

  useEffect(() => {
    loadExtras();
  }, [loadExtras]);

  const charts = insights?.charts || coverage.charts || {};

  return (
    <div className="cp-tab cp-overview" role="region" aria-label="Plan overview">
      {/* SECTION 1 — Plan Summary */}
      <section className="panel cp-tab-panel" aria-labelledby="ov-summary">
        <div className="cp-tab-panel__head">
          <div>
            <h2 id="ov-summary" className="panel__title">
              Plan summary
            </h2>
            <p className="cp-tab-lead">
              {health.readiness || "Review readiness, coverage, and next actions."}
            </p>
          </div>
          {health.score != null ? (
            <div
              className={`cp-health cp-health--lg cp-health--${health.level || "warning"}`}
              aria-label={`Health score ${health.score} percent, ${health.status}`}
            >
              <strong>{health.score}%</strong>
              <span>{health.status}</span>
            </div>
          ) : null}
        </div>
        <div className="cp-overview-grid">
          <div>
            <span className="cp-card__label">Plan name</span>
            <span className="cp-card__value">{plan.plan_name}</span>
          </div>
          <div>
            <span className="cp-card__label">Description</span>
            <span className="cp-card__value">
              {plan.description || summary.purpose || "—"}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Business unit</span>
            <span className="cp-card__value">
              {summary.business_unit || plan.business_group || "—"}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Role</span>
            <span className="cp-card__value">{plan.role || "—"}</span>
          </div>
          <div>
            <span className="cp-card__label">Current version</span>
            <span className="cp-card__value">
              {displayVersionLabel(plan)} {cv ? <VersionBadge status={cv.status} /> : null}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Effective dates</span>
            <span className="cp-card__value">
              {cv
                ? formatEffectiveRange(cv.effective_from, cv.effective_to)
                : formatEffectiveRange(plan.effective_start_date, plan.effective_end_date)}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Status</span>
            <span className="cp-card__value">{plan.status}</span>
          </div>
          <div>
            <span className="cp-card__label">Calculation method</span>
            <span className="cp-card__value">
              {summary.calculation_method || calculationMethodLabel(plan)}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Created by</span>
            <span className="cp-card__value">{plan.created_by || "—"}</span>
          </div>
          <div>
            <span className="cp-card__label">Last published</span>
            <span className="cp-card__value">
              {plan.last_published_at
                ? new Date(plan.last_published_at).toLocaleString()
                : "—"}
              {plan.last_published_by ? ` · ${plan.last_published_by}` : ""}
            </span>
          </div>
        </div>
      </section>

      {/* SECTION 7 first visually after summary when actions exist — Action Center */}
      {actions.length > 0 ? (
        <section className="panel cp-tab-panel" aria-labelledby="ov-actions">
          <h2 id="ov-actions" className="panel__title">
            Action center
          </h2>
          <p className="cp-tab-lead">What to do next to make this plan production-ready.</p>
          <div className="cp-action-grid">
            {actions.map((action) => (
              <article
                key={action.code}
                className={`cp-action-card cp-action-card--${action.severity || "warning"}`}
              >
                <h3>{action.title}</h3>
                <p>{action.detail}</p>
                <Link className="btn-primary" to={action.href}>
                  {action.cta}
                </Link>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {/* SECTION 4 — Health Score (explainable) */}
      <section className="panel cp-tab-panel" aria-labelledby="ov-health">
        <h2 id="ov-health" className="panel__title">
          Health score
        </h2>
        <div className="cp-health-explain">
          <div className={`cp-health cp-health--lg cp-health--${health.level || "warning"}`}>
            <strong>{health.score ?? "—"}%</strong>
            <span>{health.status || "—"}</span>
          </div>
          <div>
            <p className="cp-tab-lead">{health.readiness}</p>
            <ul className="cp-contributors" aria-label="Health contributors">
              {(health.contributors || []).map((c) => (
                <li
                  key={c.key}
                  className={c.ok ? "cp-contributors__ok" : "cp-contributors__miss"}
                >
                  <span aria-hidden="true">{c.ok ? "✓" : "✗"}</span>
                  {c.label}
                </li>
              ))}
            </ul>
            {(health.recommendations || []).length > 0 ? (
              <>
                <h3 className="cp-mini-chart__title">Recommendations</h3>
                <ul className="cp-recommend">
                  {health.recommendations.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        </div>
      </section>

      {/* SECTION 2 — Coverage */}
      <section className="panel cp-tab-panel" aria-labelledby="ov-coverage">
        <div className="cp-tab-panel__head">
          <div>
            <h2 id="ov-coverage" className="panel__title">
              Coverage
            </h2>
            <p className="cp-tab-lead">Who this plan reaches across the sales organization.</p>
          </div>
          <Link className="btn-secondary" to={`/comp-plans/${plan.id}/participants`}>
            View participants
          </Link>
        </div>
        <div className="cp-overview-grid">
          <div>
            <span className="cp-card__label">Employees assigned</span>
            <span className="cp-card__value">
              {coverage.employees_assigned ?? plan.participant_count ?? "—"}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Departments</span>
            <span className="cp-card__value">{formatCoverageList(coverage.departments)}</span>
          </div>
          <div>
            <span className="cp-card__label">Managers</span>
            <span className="cp-card__value">{formatCoverageList(coverage.managers)}</span>
          </div>
          <div>
            <span className="cp-card__label">Regions</span>
            <span className="cp-card__value">{formatCoverageList(coverage.regions)}</span>
          </div>
          <div>
            <span className="cp-card__label">Countries</span>
            <span className="cp-card__value">{formatCoverageList(coverage.countries)}</span>
          </div>
          <div>
            <span className="cp-card__label">Territories</span>
            <span className="cp-card__value">{formatCoverageList(coverage.territories)}</span>
          </div>
          <div>
            <span className="cp-card__label">Positions</span>
            <span className="cp-card__value">{formatCoverageList(coverage.positions)}</span>
          </div>
          <div>
            <span className="cp-card__label">Sales teams</span>
            <span className="cp-card__value">{formatCoverageList(coverage.sales_teams)}</span>
          </div>
          <div>
            <span className="cp-card__label">Business units</span>
            <span className="cp-card__value">{formatCoverageList(coverage.business_units)}</span>
          </div>
        </div>
        <div className="cp-chart-grid">
          <MiniBarChart
            title="Employees by region"
            items={charts.employees_by_region}
            ariaLabel="Employees by region chart"
          />
          <MiniBarChart
            title="Employees by department"
            items={charts.employees_by_department}
            ariaLabel="Employees by department chart"
          />
        </div>
      </section>

      {/* SECTION 3 — Configuration Health */}
      <section className="panel cp-tab-panel" aria-labelledby="ov-config">
        <div className="cp-tab-panel__head">
          <h2 id="ov-config" className="panel__title">
            Configuration health
          </h2>
          <span className="cp-card__value">
            {configHealth.overall_completion_pct ?? 0}% complete
          </span>
        </div>
        <div className="enterprise-table-wrap">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Component</th>
                <th>Status</th>
                <th>Completion</th>
                <th>Items</th>
                <th>Version</th>
                <th>Owner</th>
                <th>Last updated</th>
              </tr>
            </thead>
            <tbody>
              {(configHealth.rows || plan.components || []).map((row) => (
                <tr key={row.key}>
                  <td>{row.label}</td>
                  <td>{row.status || (row.configured ? "Configured" : "Not Configured")}</td>
                  <td>{row.completion_pct ?? (row.configured ? 100 : 0)}%</td>
                  <td>{row.items ?? row.count ?? "—"}</td>
                  <td>{row.version || displayVersionLabel(plan)}</td>
                  <td>{row.owner || plan.last_published_by || "—"}</td>
                  <td>
                    {row.last_updated
                      ? new Date(row.last_updated).toLocaleString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* SECTION 5 — Business Insights */}
      <section className="panel cp-tab-panel" aria-labelledby="ov-insights">
        <h2 id="ov-insights" className="panel__title">
          Business insights
        </h2>
        {!insights ? (
          <p className="cp-tab-lead">Loading insights…</p>
        ) : (
          <>
            <div className="cp-overview-grid">
              <div>
                <span className="cp-card__label">Employees covered</span>
                <span className="cp-card__value">{insights.employees_covered}</span>
              </div>
              <div>
                <span className="cp-card__label">Projected monthly commission</span>
                <span className="cp-card__value">
                  {formatMoney(insights.projected_monthly_commission)}
                </span>
              </div>
              <div>
                <span className="cp-card__label">Projected annual commission</span>
                <span className="cp-card__value">
                  {formatMoney(insights.projected_annual_commission)}
                </span>
              </div>
              <div>
                <span className="cp-card__label">Estimated monthly payout</span>
                <span className="cp-card__value">
                  {formatMoney(insights.estimated_monthly_payout)}
                </span>
              </div>
              <div>
                <span className="cp-card__label">Average commission</span>
                <span className="cp-card__value">{formatMoney(insights.average_commission)}</span>
              </div>
              <div>
                <span className="cp-card__label">Highest commission</span>
                <span className="cp-card__value">{formatMoney(insights.highest_commission)}</span>
              </div>
              <div>
                <span className="cp-card__label">Lowest commission</span>
                <span className="cp-card__value">{formatMoney(insights.lowest_commission)}</span>
              </div>
              <div>
                <span className="cp-card__label">Most used rate table</span>
                <span className="cp-card__value">{insights.most_used_rate_table || "—"}</span>
              </div>
              <div>
                <span className="cp-card__label">Top territories</span>
                <span className="cp-card__value">
                  {(insights.top_territories || [])
                    .map((t) => `${t.name} (${t.employees})`)
                    .join(", ") || "—"}
                </span>
              </div>
              <div>
                <span className="cp-card__label">Top products</span>
                <span className="cp-card__value">
                  {(insights.top_products || [])
                    .map((p) => `${p.name} (${p.orders})`)
                    .join(", ") || "—"}
                </span>
              </div>
              <div>
                <span className="cp-card__label">Top business unit</span>
                <span className="cp-card__value">{insights.top_business_unit || "—"}</span>
              </div>
            </div>
            <p className="cp-tab-lead">{insights.calculation_note}</p>
            <div className="cp-chart-grid">
              <MiniBarChart
                title="Commission forecast (est.)"
                items={(charts.commission_forecast || []).map((f, idx) => ({
                  label: `M+${idx}`,
                  projected: f.projected,
                }))}
              />
              <MiniBarChart
                title="Plan usage"
                items={[
                  {
                    label: "Employees",
                    count: charts.plan_usage?.employees_covered || 0,
                  },
                  {
                    label: "Commissions total",
                    count: charts.plan_usage?.commissions_total || 0,
                  },
                ]}
              />
            </div>
          </>
        )}
      </section>

      {/* SECTION 6 — Recent Activity */}
      <section className="panel cp-tab-panel" aria-labelledby="ov-activity">
        <div className="cp-tab-panel__head">
          <h2 id="ov-activity" className="panel__title">
            Recent activity
          </h2>
          <Link className="btn-secondary" to={`/comp-plans/${plan.id}/history`}>
            Full history
          </Link>
        </div>
        {activity.length === 0 ? (
          <p className="cp-tab-lead">No recent activity recorded for this plan.</p>
        ) : (
          <ol className="cp-activity-timeline">
            {activity.map((row) => (
              <li key={row.id} className="cp-activity-timeline__item">
                <span className="cp-activity-timeline__dot" aria-hidden="true" />
                <div>
                  <strong>{row.label}</strong>
                  <p className="cp-tab-lead">
                    {row.user_email || "system"}
                    {row.version_number != null ? ` · v${row.version_number}` : ""}
                  </p>
                </div>
                <time dateTime={row.created_at}>
                  {row.created_at ? new Date(row.created_at).toLocaleString() : ""}
                </time>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export default OverviewTab;
