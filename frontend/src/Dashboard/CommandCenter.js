import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { formatMoney, primaryCurrencyFromPayload } from "../utils/currency";
import {
  BUSINESS_GROUP_OPTIONS,
  businessGroupLabel,
  currencyForBusinessGroup,
} from "../utils/businessGroups";
import "./reportsAnalytics.css";
import "./commandCenter.css";

function buildLinePath(points, width, height, pad = 12) {
  if (!points.length) return "";
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = max - min || 1;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  return points
    .map((v, i) => {
      const x = pad + (i / Math.max(points.length - 1, 1)) * innerW;
      const y = pad + innerH - ((v - min) / range) * innerH;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function statusClass(code) {
  if (code === "exceeded") return "cc-status--exceeded";
  if (code === "on_track") return "cc-status--on-track";
  if (code === "at_risk") return "cc-status--at-risk";
  if (code === "below") return "cc-status--below";
  return "cc-status--unknown";
}

function ExecutiveKpis({ kpis, currency }) {
  const delta = kpis?.liability_delta_pct;
  const cards = [
    { key: "total_sales", label: "Total Sales", value: formatMoney(kpis?.total_sales, currency, { compact: true }) },
    {
      key: "commission_liability",
      label: "Commission Liability",
      value: formatMoney(kpis?.commission_liability, currency, { compact: true }),
      hint:
        delta != null
          ? `${delta >= 0 ? "↑" : "↓"} ${Math.abs(delta)}% vs previous period`
          : null,
      tone: "navy",
    },
    { key: "commission_paid", label: "Commission Paid", value: formatMoney(kpis?.commission_paid, currency, { compact: true }), tone: "teal" },
    { key: "commission_pending", label: "Commission Pending", value: formatMoney(kpis?.commission_pending, currency, { compact: true }), tone: "amber" },
    {
      key: "quota_attainment",
      label: "Quota Attainment",
      value: kpis?.quota_attainment != null ? `${kpis.quota_attainment}%` : "—",
      tone: "blue",
    },
    { key: "active_participants", label: "Active Participants", value: kpis?.active_participants ?? "—" },
    {
      key: "avg_commission_rate",
      label: "Avg Commission Rate",
      value: kpis?.avg_commission_rate != null ? `${kpis.avg_commission_rate}%` : "—",
    },
    {
      key: "leakage_risk",
      label: "Revenue Leakage Risk",
      value: (kpis?.leakage_risk || "low").toUpperCase(),
      hint: kpis?.leakage_count != null ? `${kpis.leakage_count} at-risk items` : null,
      tone: kpis?.leakage_risk === "high" ? "danger" : "amber",
    },
  ];

  return (
    <section className="cc-kpis" aria-label="Executive KPIs">
      {cards.map((c) => (
        <article key={c.key} className={`cc-kpi${c.tone ? ` cc-kpi--${c.tone}` : ""}`}>
          <span className="cc-kpi__label">{c.label}</span>
          <span className="cc-kpi__value">{c.value}</span>
          {c.hint ? <span className="cc-kpi__hint">{c.hint}</span> : null}
        </article>
      ))}
    </section>
  );
}

function CompensationHealth({ health }) {
  return (
    <section className="cc-panel">
      <div className="cc-panel__head">
        <h2>Compensation Health</h2>
        <Link className="cc-link" to="/comp-plans">
          Open plans
        </Link>
      </div>
      <div className="cc-health-grid">
        <div>
          <strong>{health?.active_plans ?? 0}</strong>
          <span>Active Plans</span>
        </div>
        <div className={health?.blocked_plans ? "is-warn" : ""}>
          <strong>{health?.blocked_plans ?? 0}</strong>
          <span>Blocked / Need Review</span>
        </div>
        <div className={health?.missing_rules ? "is-warn" : ""}>
          <strong>{health?.missing_rules ?? 0}</strong>
          <span>Missing Rules</span>
        </div>
        <div>
          <strong>{health?.pending_approvals ?? 0}</strong>
          <span>Pending Approvals</span>
        </div>
      </div>
    </section>
  );
}

function OpsAlerts({ alerts }) {
  const navigate = useNavigate();
  const rows = (alerts || []).filter((a) => a.count > 0);
  return (
    <section className="cc-panel">
      <div className="cc-panel__head">
        <h2>Commission Operations</h2>
      </div>
      {rows.length === 0 ? (
        <p className="cc-muted">No operational alerts for this period.</p>
      ) : (
        <ul className="cc-alerts">
          {rows.map((a) => (
            <li key={a.code} className={`cc-alert cc-alert--${a.severity || "low"}`}>
              <div>
                <strong>{a.title}</strong>
                <span>{a.count} item{a.count === 1 ? "" : "s"}</span>
              </div>
              <button
                type="button"
                className="ra-btn ra-btn--glass"
                onClick={() => a.href && navigate(a.href)}
              >
                {a.action_label || "Review"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function RevenueVsCommission({ series, currency }) {
  const sales = (series || []).map((r) => r.sales || 0);
  const commission = (series || []).map((r) => r.commission || 0);
  const has = sales.some((v) => v > 0) || commission.some((v) => v > 0);
  return (
    <section className="cc-panel cc-panel--wide">
      <div className="cc-panel__head">
        <h2>Revenue vs Commission</h2>
        <span className="cc-chip">{currency}</span>
      </div>
      {!has ? (
        <p className="cc-muted">No trend data for the selected period.</p>
      ) : (
        <>
          <svg viewBox="0 0 520 140" className="cc-chart" preserveAspectRatio="none">
            <path
              d={buildLinePath(sales, 520, 140)}
              fill="none"
              stroke="#0176d3"
              strokeWidth="2.5"
            />
            <path
              d={buildLinePath(commission, 520, 140)}
              fill="none"
              stroke="#0d9488"
              strokeWidth="2.5"
            />
          </svg>
          <div className="cc-legend">
            <span className="cc-legend--sales">Sales</span>
            <span className="cc-legend--comm">Commission</span>
          </div>
          <div className="cc-table-wrap">
            <table className="cc-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Sales</th>
                  <th>Commission</th>
                  <th>Commission %</th>
                </tr>
              </thead>
              <tbody>
                {(series || []).map((r) => (
                  <tr key={r.period}>
                    <td>{r.label}</td>
                    <td>{formatMoney(r.sales, currency, { compact: true })}</td>
                    <td>{formatMoney(r.commission, currency, { compact: true })}</td>
                    <td>{r.commission_pct != null ? `${r.commission_pct}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function QuotaCenter({ rows, currency, onOpen }) {
  return (
    <section className="cc-panel cc-panel--wide">
      <div className="cc-panel__head">
        <h2>Quota Attainment Center</h2>
      </div>
      {!rows?.length ? (
        <p className="cc-muted">No quota data — set personal targets in People & Access.</p>
      ) : (
        <div className="cc-table-wrap">
          <table className="cc-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Quota</th>
                <th>Achievement</th>
                <th>Attainment %</th>
                <th>Expected Commission</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 25).map((r) => (
                <tr
                  key={r.employee_id}
                  className="cc-row-click"
                  onClick={() => onOpen?.(r)}
                >
                  <td>
                    <strong>{r.employee_name}</strong>
                    <div className="cc-sub">{r.employee_id}</div>
                  </td>
                  <td>{formatMoney(r.quota, r.currency || currency, { compact: true })}</td>
                  <td>{formatMoney(r.achievement, r.currency || currency, { compact: true })}</td>
                  <td>{r.attainment_pct != null ? `${r.attainment_pct}%` : "—"}</td>
                  <td>
                    {r.expected_commission != null
                      ? formatMoney(r.expected_commission, r.currency || currency, { compact: true })
                      : "—"}
                  </td>
                  <td>
                    <span className={`cc-status ${statusClass(r.status)}`}>
                      {r.status_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function InsightsPanel({ insights, currency }) {
  return (
    <section className="cc-panel">
      <div className="cc-panel__head">
        <h2>Commission Insights</h2>
      </div>
      <div className="cc-insights">
        <div>
          <h3>Top Earners</h3>
          <ol>
            {(insights?.top_earners || []).slice(0, 5).map((e, i) => (
              <li key={e.email || i}>
                <span>{e.name}</span>
                <strong>{formatMoney(e.total, currency, { compact: true })}</strong>
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h3>Highest Revenue</h3>
          <ol>
            {(insights?.highest_revenue || []).slice(0, 5).map((e) => (
              <li key={e.employee_id}>
                <span>{e.employee_name}</span>
                <strong>{formatMoney(e.sales, currency, { compact: true })}</strong>
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h3>Largest Deals</h3>
          <ol>
            {(insights?.largest_deals || []).slice(0, 5).map((d) => (
              <li key={d.order_id}>
                <span>{d.order_id}</span>
                <strong>{formatMoney(d.sales_amount, currency, { compact: true })}</strong>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function TerritoryAnalytics({ rows, currency }) {
  return (
    <section className="cc-panel">
      <div className="cc-panel__head">
        <h2>Territory Performance</h2>
      </div>
      {!rows?.length ? (
        <p className="cc-muted">No territory sales in this period.</p>
      ) : (
        <div className="cc-table-wrap">
          <table className="cc-table">
            <thead>
              <tr>
                <th>Territory</th>
                <th>Region</th>
                <th>Sales</th>
                <th>Quota</th>
                <th>Attainment</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.territory}-${r.region}`}>
                  <td>{r.territory}</td>
                  <td>{r.region}</td>
                  <td>{formatMoney(r.sales, currency, { compact: true })}</td>
                  <td>{formatMoney(r.quota, currency, { compact: true })}</td>
                  <td>{r.attainment_pct != null ? `${r.attainment_pct}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LeaderboardTable({ rows, currency, onOpen }) {
  return (
    <section className="cc-panel cc-panel--wide">
      <div className="cc-panel__head">
        <h2>Leaderboard</h2>
      </div>
      <div className="cc-table-wrap">
        <table className="cc-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Employee</th>
              <th>Role</th>
              <th>Territory</th>
              <th>Sales</th>
              <th>Quota Attainment</th>
              <th>Commission</th>
              <th>Commission %</th>
            </tr>
          </thead>
          <tbody>
            {(rows || []).slice(0, 25).map((r, idx) => {
              const sales = r.achievement ?? r.total_sales ?? 0;
              const commission = r.expected_commission ?? r.total_commission ?? r.total ?? 0;
              const rate = sales > 0 ? ((commission / sales) * 100).toFixed(1) : null;
              return (
                <tr
                  key={r.employee_id || r.email || idx}
                  className="cc-row-click"
                  onClick={() => onOpen?.(r)}
                >
                  <td>{idx + 1}</td>
                  <td>
                    <strong>{r.employee_name || r.name}</strong>
                  </td>
                  <td>{r.role || "—"}</td>
                  <td>{r.territory || "—"}</td>
                  <td>{formatMoney(sales, r.currency || currency, { compact: true })}</td>
                  <td>{r.attainment_pct != null ? `${r.attainment_pct}%` : "—"}</td>
                  <td>{formatMoney(commission, r.currency || currency, { compact: true })}</td>
                  <td>{rate != null ? `${rate}%` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TransparencyModal({ detail, onClose, currency }) {
  if (!detail) return null;
  return (
    <div className="cc-modal" role="dialog" aria-modal="true">
      <button type="button" className="cc-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="cc-modal__panel">
        <div className="cc-panel__head">
          <div>
            <h2>{detail.employee_name}</h2>
            <p className="cc-muted">
              {detail.employee_id} · {detail.role || "—"}
              {detail.assigned_plan?.plan_name
                ? ` · ${detail.assigned_plan.plan_name}`
                : ""}
            </p>
          </div>
          <button type="button" className="ra-btn ra-btn--glass" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="cc-muted">
          Total sales: {formatMoney(detail.total_sales, currency, { compact: true })}
        </p>
        <div className="cc-table-wrap">
          <table className="cc-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Date</th>
                <th>Sales</th>
                <th>Plan / Rule</th>
                <th>Commission</th>
              </tr>
            </thead>
            <tbody>
              {(detail.transactions || []).map((t) => (
                <tr key={t.order_id}>
                  <td>{t.order_id}</td>
                  <td>{t.order_date || "—"}</td>
                  <td>{formatMoney(t.sales_amount, currency, { compact: true })}</td>
                  <td>
                    {t.plan_name || "—"}
                    {t.calculation_method ? ` · ${t.calculation_method}` : ""}
                  </td>
                  <td>
                    {t.commission_amount != null
                      ? formatMoney(t.commission_amount, currency, { compact: true })
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function CommandCenter() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [period, setPeriod] = useState("monthly");
  const [businessGroup, setBusinessGroup] = useState("all");
  const [region, setRegion] = useState("");
  const [territory, setTerritory] = useState("");
  const [plan, setPlan] = useState("");
  const [employee, setEmployee] = useState("");
  const [cc, setCc] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [drill, setDrill] = useState(null);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    if (businessGroup !== "all") params.set("business_group", businessGroup);
    if (region) params.set("region", region);
    if (territory) params.set("territory", territory);
    if (plan) params.set("plan", plan);
    if (employee) params.set("employee", employee);
    // Map period presets roughly when no explicit dates
    if (!startDate && !endDate) {
      const end = new Date();
      const start = new Date();
      if (period === "daily") start.setDate(end.getDate() - 1);
      else if (period === "weekly") start.setDate(end.getDate() - 7);
      else if (period === "quarterly") start.setMonth(end.getMonth() - 3);
      else if (period === "annual") start.setFullYear(end.getFullYear() - 1);
      else start.setMonth(end.getMonth() - 1);
      params.set("start_date", start.toISOString().slice(0, 10));
      params.set("end_date", end.toISOString().slice(0, 10));
    }
    return params.toString();
  }, [startDate, endDate, businessGroup, region, territory, plan, employee, period]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = queryString ? `?${queryString}` : "";
      const [ccRes, lbRes] = await Promise.all([
        api.get(`reports/command-center/${qs}`),
        api.get(`leaderboard/${qs}`),
      ]);
      setCc(ccRes.data);
      setLeaderboard(lbRes.data?.results || []);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load command center"));
    } finally {
      setLoading(false);
    }
  }, [queryString]);

  useEffect(() => {
    const t = setTimeout(load, employee ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, employee]);

  const currency =
    currencyForBusinessGroup(businessGroup === "all" ? "" : businessGroup, "") ||
    primaryCurrencyFromPayload(cc) ||
    "INR";

  const openEmployee = async (row) => {
    const empId = row.employee_id;
    if (!empId) return;
    try {
      const params = new URLSearchParams({ employee_id: empId });
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      // Use command center inferred dates when empty
      if (!startDate && cc?.start_date) params.set("start_date", cc.start_date);
      if (!endDate && cc?.end_date) params.set("end_date", cc.end_date);
      const res = await api.get(`reports/employee-transparency/?${params}`);
      setDrill(res.data);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load employee detail"));
    }
  };

  const exportCsv = () => {
    if (!cc) return;
    const cell = (v) => {
      const text = v == null ? "" : String(v);
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    const line = (...vals) => `${vals.map(cell).join(",")}\n`;
    let csv = line("Sales Compensation Command Center");
    csv += line("Period", `${cc.start_date} to ${cc.end_date}`);
    csv += line("Business group", businessGroupLabel(businessGroup));
    csv += "\n";
    csv += line("KPI", "Value");
    Object.entries(cc.kpis || {}).forEach(([k, v]) => {
      csv += line(k, v);
    });
    csv += "\n";
    csv += line("Quota center");
    csv += line("Employee", "Quota", "Achievement", "Attainment %", "Status");
    (cc.quota_center || []).forEach((r) => {
      csv += line(r.employee_name, r.quota, r.achievement, r.attainment_pct, r.status_label);
    });
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `command-center-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const lbRows =
    (cc?.quota_center || []).length > 0
      ? cc.quota_center
      : leaderboard.map((r) => ({
          ...r,
          employee_name: r.employee_name || r.name,
          expected_commission: r.total_commission ?? r.total,
          achievement: r.total_sales,
        }));

  return (
    <div className="cc-root">
      <header className="cc-header">
        <div className="cc-header__main">
          <div>
            <p className="cc-eyebrow">Incentra Analytics</p>
            <h1>Sales Compensation Command Center</h1>
            <p className="cc-sub">
              Monitor sales performance, commission impact, quota attainment, and payout readiness.
            </p>
          </div>
          <div className="cc-header__actions">
            <button type="button" className="ra-btn ra-btn--accent" onClick={load} disabled={loading}>
              {loading ? "Loading…" : "Refresh"}
            </button>
            <button type="button" className="ra-btn ra-btn--glass" onClick={exportCsv} disabled={!cc}>
              Export Dashboard
            </button>
          </div>
        </div>
        <div className="cc-filters">
          <label>
            Period
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
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
            <input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="e.g. Telangana" />
          </label>
          <label>
            Territory
            <input value={territory} onChange={(e) => setTerritory(e.target.value)} />
          </label>
          <label>
            Compensation Plan
            <input value={plan} onChange={(e) => setPlan(e.target.value)} placeholder="Plan name" />
          </label>
          <label>
            Employee
            <input value={employee} onChange={(e) => setEmployee(e.target.value)} placeholder="ID or search" />
          </label>
          <label>
            From
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label>
            To
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
        </div>
      </header>

      {error ? <div className="ra-error">{error}</div> : null}

      {loading && !cc ? (
        <p className="cc-muted">Loading command center…</p>
      ) : (
        <>
          <ExecutiveKpis kpis={cc?.kpis} currency={currency} />
          <div className="cc-grid">
            <CompensationHealth health={cc?.plan_health} />
            <OpsAlerts alerts={cc?.ops_alerts} />
          </div>
          <RevenueVsCommission series={cc?.revenue_vs_commission} currency={currency} />
          <QuotaCenter rows={cc?.quota_center} currency={currency} onOpen={openEmployee} />
          <div className="cc-grid">
            <InsightsPanel insights={cc?.insights} currency={currency} />
            <TerritoryAnalytics rows={cc?.territory_analytics} currency={currency} />
          </div>
          <LeaderboardTable rows={lbRows} currency={currency} onOpen={openEmployee} />
          <section className="cc-panel">
            <div className="cc-panel__head">
              <h2>Reports</h2>
            </div>
            <div className="cc-reports">
              <button type="button" className="ra-btn ra-btn--glass" onClick={exportCsv}>
                Commission / Quota Report (CSV)
              </button>
              <Link className="ra-btn ra-btn--glass" to="/orders">
                Transaction ops
              </Link>
              <Link className="ra-btn ra-btn--glass" to="/comp-plans">
                Plan effectiveness
              </Link>
            </div>
          </section>
        </>
      )}

      <TransparencyModal detail={drill} onClose={() => setDrill(null)} currency={currency} />
    </div>
  );
}

export default CommandCenter;
