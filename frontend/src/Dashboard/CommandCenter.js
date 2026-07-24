import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { formatMoney, primaryCurrencyFromPayload } from "../utils/currency";
import {
  BUSINESS_GROUP_OPTIONS,
  businessGroupLabel,
  currencyForBusinessGroup,
} from "../utils/businessGroups";
import "./commandCenter.css";

const LazyCharts = lazy(() => import("./CommandCenterCharts"));

function buildSparkPath(points, width = 64, height = 24) {
  if (!points?.length) return "";
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = max - min || 1;
  return points
    .map((v, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function formatKpiValue(card, currency) {
  if (card.value == null) return "—";
  if (card.format === "percent") return `${card.value}%`;
  if (card.format === "number") return Number(card.value).toLocaleString();
  return formatMoney(card.value, currency, { compact: true });
}

function DeltaLine({ delta, explanation }) {
  if (delta == null) {
    return <span className="ecc-delta is-none">No comparison available</span>;
  }
  const up = delta >= 0;
  return (
    <span className={`ecc-delta ${up ? "is-up" : "is-down"}`}>
      <strong>
        {up ? "↑" : "↓"} {Math.abs(delta)}%
      </strong>
      <span>{explanation || "vs last period"}</span>
    </span>
  );
}

function ExecutiveKpiGrid({ cards, currency, onDrill }) {
  return (
    <section className="ecc-kpis" aria-label="Executive KPIs">
      {(cards || []).map((c) => (
        <article
          key={c.key}
          className={`ecc-kpi status-${c.status || "neutral"}`}
          role="button"
          tabIndex={0}
          onClick={() => onDrill?.(c.href)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") onDrill?.(c.href);
          }}
        >
          <div className="ecc-kpi__top">
            <span className="ecc-kpi__label">{c.label}</span>
            <span className={`ecc-kpi__pill status-${c.status || "neutral"}`}>
              {c.status === "attention"
                ? "Watch"
                : c.status === "up"
                  ? "Up"
                  : c.status === "down"
                    ? "Down"
                    : c.status === "stable"
                      ? "Stable"
                      : "—"}
            </span>
          </div>
          <div className="ecc-kpi__value">{formatKpiValue(c, currency)}</div>
          <div className="ecc-kpi__foot">
            <DeltaLine delta={c.delta_pct} explanation={c.explanation} />
            {c.sparkline?.length > 1 ? (
              <svg className="ecc-spark" viewBox="0 0 64 24" aria-hidden>
                <path
                  d={buildSparkPath(c.sparkline)}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                />
              </svg>
            ) : (
              <span className="ecc-spark-placeholder" />
            )}
          </div>
        </article>
      ))}
    </section>
  );
}

function ActionCenter({ alerts, currency }) {
  const buckets = useMemo(() => {
    const list = alerts || [];
    return {
      critical: list.filter((a) => a.severity === "high"),
      warning: list.filter((a) => a.severity === "medium"),
      info: list.filter((a) => a.severity === "low" || !a.severity),
    };
  }, [alerts]);

  const renderBucket = (key, title, items) => (
    <div className={`ecc-action-col sev-${key}`}>
      <header>
        <i aria-hidden />
        <h3>{title}</h3>
        <span>{items.length}</span>
      </header>
      {!items.length ? (
        <p className="ecc-quiet">None</p>
      ) : (
        <ul>
          {items.map((a) => (
            <li key={a.code}>
              <Link to={a.href || "/commissions"} className="ecc-action-item">
                <strong>{a.title}</strong>
                <span>
                  {a.count} {a.count === 1 ? "item" : "items"}
                  {a.impact_amount != null && a.impact_amount > 0
                    ? ` · ${formatMoney(a.impact_amount, currency, { compact: true })}`
                    : ""}
                </span>
                <em>{a.action_label || "Review"}</em>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Action Center</h2>
      </div>
      <div className="ecc-actions">
        {renderBucket("critical", "Critical", buckets.critical)}
        {renderBucket("warning", "Warnings", buckets.warning)}
        {renderBucket("info", "Information", buckets.info)}
      </div>
    </section>
  );
}

function QuotaPerformance({ distribution, employees, currency, avg }) {
  const bands = [
    { key: "over_achievers", label: "Above Target", color: "#0f766e" },
    { key: "on_track", label: "On Track", color: "#1d4ed8" },
    { key: "at_risk", label: "At Risk", color: "#b45309" },
    { key: "critical", label: "Critical", color: "#b91c1c" },
  ];
  const total = bands.reduce((s, b) => s + (distribution?.[b.key] || 0), 0) || 1;
  let angle = -90;
  const arcs = bands.map((b) => {
    const count = distribution?.[b.key] || 0;
    const sweep = (count / total) * 360;
    const start = angle;
    angle += sweep;
    return { ...b, count, start, sweep };
  });

  const describeArc = (startDeg, sweepDeg, r = 42) => {
    if (sweepDeg <= 0) return "";
    const toRad = (d) => (d * Math.PI) / 180;
    const x1 = 50 + r * Math.cos(toRad(startDeg));
    const y1 = 50 + r * Math.sin(toRad(startDeg));
    const x2 = 50 + r * Math.cos(toRad(startDeg + sweepDeg));
    const y2 = 50 + r * Math.sin(toRad(startDeg + sweepDeg));
    const large = sweepDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  const rows = (employees || []).slice(0, 8);

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Quota Performance</h2>
        <span className="ecc-metric-chip">{avg != null ? `${avg}% avg` : "—"}</span>
      </div>
      <div className="ecc-quota">
        <div className="ecc-donut-wrap">
          <svg viewBox="0 0 100 100" className="ecc-donut" aria-hidden>
            <circle cx="50" cy="50" r="42" fill="none" stroke="#e8edf3" strokeWidth="10" />
            {arcs.map((a) =>
              a.sweep > 0 ? (
                <path
                  key={a.key}
                  d={describeArc(a.start, Math.max(a.sweep - 0.6, 0.1))}
                  fill="none"
                  stroke={a.color}
                  strokeWidth="10"
                  strokeLinecap="butt"
                />
              ) : null
            )}
            <text x="50" y="48" textAnchor="middle" className="ecc-donut__val">
              {avg != null ? `${avg}%` : "—"}
            </text>
            <text x="50" y="58" textAnchor="middle" className="ecc-donut__sub">
              Attainment
            </text>
          </svg>
          <ul className="ecc-legend">
            {bands.map((b) => (
              <li key={b.key}>
                <i style={{ background: b.color }} />
                <span>{b.label}</span>
                <strong>{distribution?.[b.key] || 0}</strong>
              </li>
            ))}
          </ul>
        </div>
        <div className="ecc-table-wrap">
          <table className="ecc-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Quota</th>
                <th>Achievement</th>
                <th>Attainment</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {!rows.length ? (
                <tr>
                  <td colSpan={5} className="ecc-quiet">
                    No employee quota data
                  </td>
                </tr>
              ) : (
                rows.map((r) => {
                  const pct = r.attainment_pct;
                  const width = Math.min(Math.max(pct || 0, 0), 100);
                  return (
                    <tr key={r.employee_id || r.email}>
                      <td>
                        <strong>{r.employee_name || r.email}</strong>
                      </td>
                      <td>{formatMoney(r.quota, currency, { compact: true })}</td>
                      <td>{formatMoney(r.achievement, currency, { compact: true })}</td>
                      <td>
                        <div className="ecc-bar">
                          <span>{pct != null ? `${pct}%` : "—"}</span>
                          <div className="ecc-bar__track">
                            <i
                              className={`status-${r.status || "unknown"}`}
                              style={{ width: `${width}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`ecc-status status-${r.status || "unknown"}`}>
                          {r.status_label || "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function TerritoryCards({ board, currency }) {
  const [mode, setMode] = useState("top");
  const rows = (mode === "top" ? board?.top : board?.worst) || [];

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Territory Analytics</h2>
        <div className="ecc-seg">
          <button type="button" className={mode === "top" ? "is-active" : ""} onClick={() => setMode("top")}>
            Top
          </button>
          <button
            type="button"
            className={mode === "worst" ? "is-active" : ""}
            onClick={() => setMode("worst")}
          >
            Lowest
          </button>
        </div>
      </div>
      {!rows.length ? (
        <p className="ecc-quiet">No territory data</p>
      ) : (
        <div className="ecc-terr-cards">
          {rows.slice(0, 6).map((r) => (
            <article key={`${r.territory}-${r.region}`} className="ecc-terr-card">
              <h3>{r.territory}</h3>
              <p className="ecc-quiet">{r.region}</p>
              <dl>
                <div>
                  <dt>Revenue</dt>
                  <dd>{formatMoney(r.sales, currency, { compact: true })}</dd>
                </div>
                <div>
                  <dt>Growth</dt>
                  <dd>
                    {r.growth_pct != null
                      ? `${r.growth_pct >= 0 ? "+" : ""}${r.growth_pct}%`
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Attainment</dt>
                  <dd>{r.attainment_pct != null ? `${r.attainment_pct}%` : "—"}</dd>
                </div>
                <div>
                  <dt>Commission</dt>
                  <dd>{formatMoney(r.commission || 0, currency, { compact: true })}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function PlanPerformanceTable({ plans, currency }) {
  const [sortKey, setSortKey] = useState("revenue_generated");
  const [asc, setAsc] = useState(false);
  const rows = useMemo(() => {
    const list = [...(plans || [])];
    list.sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      if (typeof av === "string") return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      return asc ? av - bv : bv - av;
    });
    return list.slice(0, 10);
  }, [plans, sortKey, asc]);

  const sort = (key) => {
    if (sortKey === key) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(false);
    }
  };

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Compensation Plan Performance</h2>
        <Link className="ecc-ghost-link" to="/comp-plans">
          Plans
        </Link>
      </div>
      <div className="ecc-table-wrap">
        <table className="ecc-table ecc-table--plans">
          <thead>
            <tr>
              <th>
                <button type="button" onClick={() => sort("plan_name")}>
                  Plan
                </button>
              </th>
              <th>
                <button type="button" onClick={() => sort("revenue_generated")}>
                  Revenue
                </button>
              </th>
              <th>
                <button type="button" onClick={() => sort("commission_cost")}>
                  Commission Cost
                </button>
              </th>
              <th>
                <button type="button" onClick={() => sort("employees_covered")}>
                  Employees
                </button>
              </th>
              <th>
                <button type="button" onClick={() => sort("roi")}>
                  ROI
                </button>
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {!rows.length ? (
              <tr>
                <td colSpan={6} className="ecc-quiet">
                  No plan performance data
                </td>
              </tr>
            ) : (
              rows.map((p) => (
                <tr key={p.plan_id}>
                  <td>
                    <strong>{p.plan_name}</strong>
                  </td>
                  <td>{formatMoney(p.revenue_generated, currency, { compact: true })}</td>
                  <td>{formatMoney(p.commission_cost, currency, { compact: true })}</td>
                  <td>{p.employees_covered ?? "—"}</td>
                  <td>{p.roi_label || "—"}</td>
                  <td>
                    <span
                      className={`ecc-status ${
                        p.status === "Needs Review"
                          ? "status-critical"
                          : p.status === "Healthy"
                            ? "status-over_achiever"
                            : "status-on_track"
                      }`}
                    >
                      {p.status || "—"}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function InsightCards({ items }) {
  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Executive Insights</h2>
      </div>
      <div className="ecc-insight-grid">
        {(items || []).map((i) => (
          <article key={i.code} className={`ecc-insight tone-${i.tone || "neutral"}`}>
            <span className="ecc-insight__dot" aria-hidden />
            <div>
              <h3>{i.title || "Insight"}</h3>
              <p>{i.text}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ActivityTimeline({ items }) {
  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Recent Activity</h2>
        <Link className="ecc-ghost-link" to="/audit-logs">
          Activity
        </Link>
      </div>
      {!items?.length ? (
        <p className="ecc-quiet">No recent activity</p>
      ) : (
        <ol className="ecc-timeline">
          {items.map((ev) => {
            const t = ev.at ? new Date(ev.at) : null;
            const time =
              t && !Number.isNaN(t.getTime())
                ? t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                : "—";
            return (
              <li key={ev.id || `${ev.action}-${ev.at}`}>
                <time>{time}</time>
                <span>{ev.label || ev.action}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function CommandCenter() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState("monthly");
  const [businessGroup, setBusinessGroup] = useState("all");
  const [region, setRegion] = useState("");
  const [cc, setCc] = useState(null);
  const [chartsReady, setChartsReady] = useState(false);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (businessGroup !== "all") params.set("business_group", businessGroup);
    if (region) params.set("region", region);
    const end = new Date();
    const start = new Date();
    if (period === "quarterly") start.setMonth(end.getMonth() - 3);
    else if (period === "annual") start.setFullYear(end.getFullYear() - 1);
    else if (period === "rolling12") start.setMonth(end.getMonth() - 12);
    else start.setMonth(end.getMonth() - 1);
    params.set("start_date", start.toISOString().slice(0, 10));
    params.set("end_date", end.toISOString().slice(0, 10));
    return params.toString();
  }, [businessGroup, region, period]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = queryString ? `?${queryString}` : "";
      const ccRes = await api.get(`reports/command-center/${qs}`);
      setCc(ccRes.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load dashboard"));
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const id = window.setTimeout(() => setChartsReady(true), 40);
    return () => window.clearTimeout(id);
  }, []);

  const currency =
    currencyForBusinessGroup(businessGroup === "all" ? "" : businessGroup, "") ||
    primaryCurrencyFromPayload(cc) ||
    "INR";

  const kpiCards = cc?.executive_kpis?.length
    ? cc.executive_kpis
    : [
        {
          key: "revenue",
          label: "Revenue",
          value: cc?.kpis?.total_sales,
          format: "money",
          delta_pct: cc?.kpis?.sales_delta_pct,
          status: "neutral",
          explanation: "vs last period",
          sparkline: [],
          href: "/orders",
        },
        {
          key: "liability",
          label: "Commission Liability",
          value: cc?.kpis?.commission_liability,
          format: "money",
          delta_pct: cc?.kpis?.liability_delta_pct,
          status: "neutral",
          href: "/commissions",
        },
        {
          key: "paid",
          label: "Commission Paid",
          value: cc?.kpis?.commission_paid,
          format: "money",
          delta_pct: cc?.kpis?.paid_delta_pct,
          status: "neutral",
          href: "/payouts",
        },
        {
          key: "forecast",
          label: "Forecasted Commission",
          value: cc?.kpis?.forecasted_commission,
          format: "money",
          delta_pct: null,
          status: "neutral",
          href: "/commissions",
        },
        {
          key: "attainment",
          label: "Quota Attainment",
          value: cc?.kpis?.quota_attainment,
          format: "percent",
          delta_pct: cc?.kpis?.attainment_delta_pct,
          status: "neutral",
          href: "/user-setup",
        },
        {
          key: "active_plans",
          label: "Active Plans",
          value: cc?.kpis?.active_plans,
          format: "number",
          delta_pct: null,
          status: "neutral",
          href: "/comp-plans",
        },
        {
          key: "employees",
          label: "Employees Covered",
          value: cc?.kpis?.active_participants,
          format: "number",
          delta_pct: cc?.kpis?.participants_delta_pct,
          status: "neutral",
          href: "/user-setup",
        },
        {
          key: "pending_actions",
          label: "Pending Actions",
          value: cc?.action_center?.length || 0,
          format: "number",
          delta_pct: null,
          status: "neutral",
          href: "/commissions",
        },
      ];

  const costRatio = cc?.kpis?.avg_commission_rate;

  return (
    <div className="ecc-root">
      <header className="ecc-header">
        <div className="ecc-header__main">
          <div>
            <h1>Performance Command Center</h1>
            <p className="ecc-sub">Business performance and exceptions requiring action</p>
          </div>
          <button type="button" className="ecc-btn" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        <div className="ecc-filters">
          <label>
            Period
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="monthly">Month</option>
              <option value="quarterly">Quarter</option>
              <option value="annual">Year</option>
              <option value="rolling12">Rolling 12</option>
            </select>
          </label>
          <label>
            Business Unit
            <select value={businessGroup} onChange={(e) => setBusinessGroup(e.target.value)}>
              <option value="all">All</option>
              {BUSINESS_GROUP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Region
            <input
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="All regions"
            />
          </label>
        </div>
      </header>

      {error ? <div className="ecc-error">{error}</div> : null}

      {loading && !cc ? (
        <p className="ecc-quiet">Loading…</p>
      ) : (
        <>
          <ExecutiveKpiGrid
            cards={kpiCards}
            currency={currency}
            onDrill={(href) => href && navigate(href)}
          />

          {chartsReady ? (
            <Suspense fallback={<div className="ecc-panel ecc-chart-skeleton">Loading charts…</div>}>
              <LazyCharts
                series={cc?.trend_series || cc?.revenue_vs_commission}
                currency={currency}
                costRatio={costRatio}
                period={period}
                onPeriodChange={setPeriod}
              />
            </Suspense>
          ) : (
            <div className="ecc-panel ecc-chart-skeleton">Loading charts…</div>
          )}

          <ActionCenter alerts={cc?.action_center} currency={currency} />

          <QuotaPerformance
            distribution={cc?.attainment_distribution}
            employees={cc?.quota_center || cc?.top_performers}
            currency={currency}
            avg={cc?.kpis?.quota_attainment}
          />

          <TerritoryCards board={cc?.territory_board} currency={currency} />

          <PlanPerformanceTable
            plans={cc?.plan_performance}
            currency={currency}
          />

          <div className="ecc-bottom-grid">
            <InsightCards items={cc?.executive_insights} />
            <ActivityTimeline items={cc?.recent_activity} />
          </div>

          <p className="ecc-footer-meta">
            {cc?.start_date} → {cc?.end_date}
            {businessGroup !== "all" ? ` · ${businessGroupLabel(businessGroup)}` : ""}
          </p>
        </>
      )}
    </div>
  );
}

export default CommandCenter;
