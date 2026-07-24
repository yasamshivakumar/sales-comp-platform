import { lazy, Suspense, useCallback, useEffect, useMemo, useState, Fragment } from "react";
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

function buildSparkPath(points, width = 80, height = 30) {
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
  if (card.value == null || card.value === "") return "—";
  if (card.format === "text") return String(card.value);
  if (card.format === "percent") return `${card.value}%`;
  if (card.format === "number") return Number(card.value).toLocaleString();
  return formatMoney(card.value, currency, { compact: true });
}

function statusDotClass(status, key, value) {
  if (key === "risk") {
    const v = String(value || status || "").toLowerCase();
    if (v.includes("high") || status === "attention") return "is-bad";
    if (v.includes("medium") || status === "down") return "is-warn";
    return "is-good";
  }
  if (status === "attention" || status === "down") return "is-warn";
  if (status === "up" || status === "stable") return "is-good";
  return "is-neutral";
}

function emptyLabel(value, fallback = "No previous period") {
  if (value == null || value === "" || value === "—") return fallback;
  return value;
}

function ExecutiveKpiHeader({ cards, currency, onDrill }) {
  return (
    <section className="ecc-kpi-strip" aria-label="Executive KPIs">
      {(cards || []).slice(0, 6).map((c) => (
        <article
          key={c.key}
          className={`ecc-kpi ecc-kpi--${c.key}`}
          role="button"
          tabIndex={0}
          onClick={() => onDrill?.(c.href)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") onDrill?.(c.href);
          }}
        >
          <div className="ecc-kpi__top">
            <span className="ecc-kpi__label">{c.label}</span>
            <i
              className={`ecc-kpi__dot ${statusDotClass(c.status, c.key, c.value)}`}
              aria-hidden
            />
          </div>
          <div
            className={`ecc-kpi__value ${
              c.format === "text" ? `risk-${String(c.value).toLowerCase()}` : ""
            }`}
          >
            {formatKpiValue(c, currency)}
          </div>
          <div className="ecc-kpi__context">
            <span>{emptyLabel(c.context, "No previous period")}</span>
            {c.context_status ? (
              <em className={`ecc-kpi__badge status-${String(c.context_status).toLowerCase()}`}>
                {c.context_status}
              </em>
            ) : null}
          </div>
          {c.sparkline?.length > 1 ? (
            <svg className="ecc-spark" viewBox="0 0 80 30" aria-hidden>
              <path d={buildSparkPath(c.sparkline)} fill="none" stroke="currentColor" strokeWidth="1.75" />
            </svg>
          ) : (
            <div className="ecc-spark-spacer" />
          )}
        </article>
      ))}
    </section>
  );
}

function HealthScore({ health }) {
  const score = health?.score ?? 0;
  const r = 58;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.max(0, Math.min(100, score)) / 100) * c;
  const tone =
    score >= 80 ? "good" : score >= 65 ? "stable" : score >= 45 ? "warn" : "bad";

  return (
    <section className="ecc-panel ecc-health">
      <h2>Business Health Score</h2>
      <div className="ecc-health__ring-wrap">
        <svg viewBox="0 0 150 150" className="ecc-health__ring" aria-hidden>
          <circle cx="75" cy="75" r={r} fill="none" stroke="#e8edf3" strokeWidth="11" />
          <circle
            cx="75"
            cy="75"
            r={r}
            fill="none"
            stroke="currentColor"
            strokeWidth="11"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={offset}
            transform="rotate(-90 75 75)"
            className={`tone-${tone}`}
          />
        </svg>
        <div className="ecc-health__center">
          <strong>{score}</strong>
          <span>{health?.label || "—"}</span>
        </div>
      </div>
      <ul className="ecc-health__parts">
        {(health?.components || []).map((p) => (
          <li key={p.code}>
            <div className="ecc-health__part-head">
              <span>{p.label}</span>
              <strong>{p.score}</strong>
            </div>
            <div className="ecc-health__bar">
              <i style={{ width: `${Math.min(100, Math.max(0, p.score || 0))}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ActionPanel({ alerts, currency }) {
  const items = useMemo(() => {
    const list = [...(alerts || [])];
    list.sort((a, b) => (a.severity_rank || 9) - (b.severity_rank || 9));
    return list.slice(0, 6);
  }, [alerts]);

  const sevLabel = (s) => (s === "high" ? "Critical" : s === "medium" ? "Warning" : "Information");
  const cta = (s, code) => {
    if (code === "missing_quota") return "Configure";
    if (s === "high") return "Resolve";
    if (s === "medium") return "Review";
    return "Open";
  };

  return (
    <aside className="ecc-panel ecc-action-panel">
      <div className="ecc-panel__head">
        <h2>Action Center</h2>
        <span className="ecc-count">{items.length}</span>
      </div>
      {!items.length ? (
        <div className="ecc-empty-ok">
          <strong>All clear</strong>
          <p>No exceptions require attention</p>
        </div>
      ) : (
        <ul className="ecc-action-list">
          {items.map((a) => (
            <li key={a.code} className={`sev-${a.severity || "low"}`}>
              <span className="ecc-action-list__sev">{sevLabel(a.severity)}</span>
              <strong>{a.title}</strong>
              <span className="ecc-action-list__meta">
                {a.count} {a.count === 1 ? "item" : "items"}
                {a.impact_amount != null && a.impact_amount > 0
                  ? ` · ${formatMoney(a.impact_amount, currency, { compact: true })} impact`
                  : ""}
              </span>
              <Link className="ecc-action-list__cta" to={a.href || "/commissions"}>
                {a.action_label || cta(a.severity, a.code)}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

function QuotaBoard({ distribution, employees, avg, currency }) {
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

  const describeArc = (startDeg, sweepDeg, r = 40) => {
    if (sweepDeg <= 0) return "";
    const toRad = (d) => (d * Math.PI) / 180;
    const x1 = 50 + r * Math.cos(toRad(startDeg));
    const y1 = 50 + r * Math.sin(toRad(startDeg));
    const x2 = 50 + r * Math.cos(toRad(startDeg + sweepDeg));
    const y2 = 50 + r * Math.sin(toRad(startDeg + sweepDeg));
    const large = sweepDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  const rows = (employees || []).slice(0, 6);

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Quota Attainment Distribution</h2>
      </div>
      <div className="ecc-quota-board">
        <div className="ecc-quota-board__donut">
          <svg viewBox="0 0 100 100" className="ecc-donut" aria-hidden>
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e8edf3" strokeWidth="9" />
            {arcs.map((a) =>
              a.sweep > 0 ? (
                <path
                  key={a.key}
                  d={describeArc(a.start, Math.max(a.sweep - 0.8, 0.1))}
                  fill="none"
                  stroke={a.color}
                  strokeWidth="9"
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
                {b.label}
                <strong>{distribution?.[b.key] || 0}</strong>
              </li>
            ))}
          </ul>
        </div>
        <div className="ecc-leaderboard">
          <div className="ecc-leaderboard__head ecc-leaderboard__head--4">
            <span>Employee</span>
            <span>Quota</span>
            <span>Achievement</span>
            <span>Attainment</span>
          </div>
          {!rows.length ? (
            <p className="ecc-quiet">No top performers for this period</p>
          ) : (
            rows.map((r) => {
              const pct = r.attainment_pct;
              const width = Math.min(Math.max(pct || 0, 0), 100);
              return (
                <div key={r.employee_id || r.email} className="ecc-leaderboard__row ecc-leaderboard__row--4">
                  <div>
                    <strong>{r.employee_name || r.email}</strong>
                    <span className={`ecc-status status-${r.status || "unknown"}`}>
                      {r.status_label || "—"}
                    </span>
                  </div>
                  <span>{formatMoney(r.quota, currency, { compact: true })}</span>
                  <span>{formatMoney(r.achievement, currency, { compact: true })}</span>
                  <div className="ecc-hbar">
                    <span>{pct != null ? `${pct}%` : "No target"}</span>
                    <div className="ecc-hbar__track">
                      <i className={`status-${r.status || "unknown"}`} style={{ width: `${width}%` }} />
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}

function TerritoryRanking({ board, currency }) {
  const [mode, setMode] = useState("top");
  const rows = (mode === "top" ? board?.top : board?.worst) || [];
  const maxSales = Math.max(...rows.map((r) => r.sales || 0), 1);

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Territory Analytics</h2>
        <div className="ecc-seg">
          <button type="button" className={mode === "top" ? "is-active" : ""} onClick={() => setMode("top")}>
            Top
          </button>
          <button type="button" className={mode === "worst" ? "is-active" : ""} onClick={() => setMode("worst")}>
            Lowest
          </button>
        </div>
      </div>
      {!rows.length ? (
        <p className="ecc-quiet">No territory data</p>
      ) : (
        <ol className="ecc-rank">
          {rows.slice(0, 5).map((r, idx) => (
            <li key={`${r.territory}-${r.region}`}>
              <span className="ecc-rank__n">{idx + 1}</span>
              <div className="ecc-rank__body">
                <div className="ecc-rank__title">
                  <strong>{r.territory}</strong>
                  <span>{formatMoney(r.sales, currency, { compact: true })}</span>
                </div>
                <div className="ecc-rank__bar">
                  <i style={{ width: `${Math.round(((r.sales || 0) / maxSales) * 100)}%` }} />
                </div>
                <div className="ecc-rank__meta">
                  <span>
                    Quota{" "}
                    {r.attainment_pct != null ? `${r.attainment_pct}%` : "No target"}
                  </span>
                  <span>
                    Commission Efficiency{" "}
                    {r.commission_pct != null ? `${r.commission_pct}%` : "No data"}
                  </span>
                  <span>
                    Trend{" "}
                    {r.growth_pct != null
                      ? `${r.growth_pct >= 0 ? "+" : ""}${r.growth_pct}%`
                      : "No previous period"}
                  </span>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function PlanTable({ plans, currency }) {
  const [sortKey, setSortKey] = useState("revenue_generated");
  const [asc, setAsc] = useState(false);
  const [q, setQ] = useState("");
  const [healthFilter, setHealthFilter] = useState("all");
  const [openId, setOpenId] = useState(null);

  const rows = useMemo(() => {
    let list = [...(plans || [])];
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      list = list.filter((p) => (p.plan_name || "").toLowerCase().includes(needle));
    }
    if (healthFilter !== "all") {
      list = list.filter((p) => (p.status || "") === healthFilter);
    }
    list.sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      if (typeof av === "string") return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      return asc ? av - bv : bv - av;
    });
    return list.slice(0, 8);
  }, [plans, sortKey, asc, q, healthFilter]);

  const sort = (key) => {
    if (sortKey === key) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(false);
    }
  };

  const badgeClass = (s) =>
    s === "Needs Review" ? "status-critical" : s === "Healthy" ? "status-over_achiever" : "status-on_track";

  return (
    <section className="ecc-panel">
      <div className="ecc-panel__head">
        <h2>Compensation Plan Performance</h2>
        <Link className="ecc-ghost-link" to="/comp-plans">
          Plans
        </Link>
      </div>
      <div className="ecc-table-tools">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search plans"
          aria-label="Search plans"
        />
        <select value={healthFilter} onChange={(e) => setHealthFilter(e.target.value)}>
          <option value="all">All health</option>
          <option value="Healthy">Healthy</option>
          <option value="Monitor">Monitor</option>
          <option value="Needs Review">Needs Review</option>
        </select>
      </div>
      <div className="ecc-table-wrap">
        <table className="ecc-table">
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
                <button type="button" onClick={() => sort("roi")}>
                  ROI
                </button>
              </th>
              <th>
                <button type="button" onClick={() => sort("employees_covered")}>
                  Employees
                </button>
              </th>
              <th>
                <button type="button" onClick={() => sort("attainment_pct")}>
                  Attainment
                </button>
              </th>
              <th>Health</th>
            </tr>
          </thead>
          <tbody>
            {!rows.length ? (
              <tr>
                <td colSpan={7} className="ecc-quiet">
                  No plans match
                </td>
              </tr>
            ) : (
              rows.map((p) => (
                <Fragment key={p.plan_id}>
                  <tr
                    className={`ecc-table__row ${openId === p.plan_id ? "is-open" : ""}`}
                    onClick={() => setOpenId(openId === p.plan_id ? null : p.plan_id)}
                  >
                    <td>
                      <strong>{p.plan_name}</strong>
                    </td>
                    <td>{formatMoney(p.revenue_generated, currency, { compact: true })}</td>
                    <td>{formatMoney(p.commission_cost, currency, { compact: true })}</td>
                    <td>{p.roi_label || "No ROI"}</td>
                    <td>{p.employees_covered ?? 0}</td>
                    <td>
                      {p.attainment_pct != null ? `${p.attainment_pct}%` : "No target"}
                    </td>
                    <td>
                      <span className={`ecc-status ${badgeClass(p.status)}`}>{p.status || "—"}</span>
                    </td>
                  </tr>
                  {openId === p.plan_id ? (
                    <tr className="ecc-table__detail">
                      <td colSpan={7}>
                        <div className="ecc-plan-detail">
                          <div>
                            <span>Cost ratio</span>
                            <strong>
                              {p.commission_ratio_pct != null
                                ? `${p.commission_ratio_pct}%`
                                : "No revenue"}
                            </strong>
                          </div>
                          <div>
                            <span>Employees covered</span>
                            <strong>{p.employees_covered ?? 0}</strong>
                          </div>
                          <div>
                            <span>Health</span>
                            <strong>{p.status}</strong>
                          </div>
                          <Link to="/comp-plans" className="ecc-insight__cta">
                            Open plan workspace
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
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
        {(items || []).slice(0, 4).map((i) => (
          <article key={i.code} className={`ecc-insight tone-${i.tone || "neutral"}`}>
            <span className="ecc-insight__dot" aria-hidden />
            <div className="ecc-insight__body">
              <h3>{i.title || "Insight"}</h3>
              <p className="ecc-insight__text">{i.text}</p>
              {i.reason ? (
                <p className="ecc-insight__reason">
                  <span>Reason</span> {i.reason}
                </p>
              ) : null}
              {i.href ? (
                <Link className="ecc-insight__cta" to={i.href}>
                  {i.cta || "Open"}
                </Link>
              ) : null}
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
        <h2>Business Activity</h2>
        <Link className="ecc-ghost-link" to="/audit-logs">
          Full audit
        </Link>
      </div>
      {!items?.length ? (
        <p className="ecc-quiet">No recent business events</p>
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
  const [refreshedAt, setRefreshedAt] = useState(null);

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
      setRefreshedAt(new Date());
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

  const refreshedLabel = useMemo(() => {
    const t = refreshedAt || (cc?.generated_at ? new Date(cc.generated_at) : null);
    if (!t || Number.isNaN(t.getTime())) return "—";
    return t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }, [refreshedAt, cc?.generated_at]);

  const dataStatus = cc?.business_health?.data_status || "Healthy";

  const kpiCards = useMemo(() => {
    if (cc?.executive_kpis?.length) return cc.executive_kpis;
    return [];
  }, [cc]);

  return (
    <div className="ecc-root">
      <header className="ecc-header">
        <div className="ecc-header__main">
          <div>
            <h1>Executive Performance Overview</h1>
            <p className="ecc-sub">
              Real-time visibility into revenue performance, compensation cost, quota attainment,
              and operational risks.
            </p>
            <div className="ecc-header__meta">
              <span>
                Last refreshed: <strong>{refreshedLabel}</strong>
              </span>
              <span className={`ecc-data-status is-${String(dataStatus).toLowerCase()}`}>
                Data status: <strong>{dataStatus}</strong>
              </span>
            </div>
          </div>
          <div className="ecc-header__actions">
            <div className="ecc-filters ecc-filters--inline">
              <select value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Period">
                <option value="monthly">Month</option>
                <option value="quarterly">Quarter</option>
                <option value="annual">Year</option>
                <option value="rolling12">Rolling 12</option>
              </select>
              <select
                value={businessGroup}
                onChange={(e) => setBusinessGroup(e.target.value)}
                aria-label="Business unit"
              >
                <option value="all">All units</option>
                {BUSINESS_GROUP_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="Region"
                aria-label="Region"
              />
            </div>
            <button type="button" className="ecc-btn" onClick={load} disabled={loading}>
              {loading ? "…" : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      {error ? <div className="ecc-error">{error}</div> : null}

      {loading && !cc ? (
        <p className="ecc-quiet">Loading command center…</p>
      ) : (
        <>
          <ExecutiveKpiHeader
            cards={kpiCards}
            currency={currency}
            onDrill={(href) => href && navigate(href)}
          />

          <div className="ecc-cockpit">
            <HealthScore health={cc?.business_health} />
            {chartsReady ? (
              <Suspense fallback={<div className="ecc-panel ecc-chart-skeleton">Loading trend…</div>}>
                <LazyCharts
                  series={cc?.trend_series || cc?.revenue_vs_commission}
                  previousSeries={cc?.previous_trend_series}
                  currency={currency}
                  period={period}
                  onPeriodChange={setPeriod}
                  rangeLabel={`${cc?.start_date || ""} → ${cc?.end_date || ""}`}
                />
              </Suspense>
            ) : (
              <div className="ecc-panel ecc-chart-skeleton">Loading trend…</div>
            )}
            <ActionPanel alerts={cc?.action_center} currency={currency} />
          </div>

          <div className="ecc-mid">
            <QuotaBoard
              distribution={cc?.attainment_distribution}
              employees={cc?.quota_center}
              avg={cc?.kpis?.quota_attainment}
              currency={currency}
            />
            <TerritoryRanking board={cc?.territory_board} currency={currency} />
          </div>

          <PlanTable plans={cc?.plan_performance} currency={currency} />

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
