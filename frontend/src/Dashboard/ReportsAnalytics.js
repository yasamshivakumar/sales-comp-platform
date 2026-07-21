import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import {
  activeCurrencyTotals,
  formatMoney,
  formatDashboardAmount,
  formatMoneyList,
  primaryCurrencyFromPayload,
} from "../utils/currency";
import {
  BUSINESS_GROUP_OPTIONS,
  businessGroupLabel,
  currencyForBusinessGroup,
} from "../utils/businessGroups";
import "./reportsAnalytics.css";

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

function buildAreaPath(points, width, height, pad = 12) {
  const line = buildLinePath(points, width, height, pad);
  if (!line) return "";
  const lastX = width - pad;
  const baseY = height - pad;
  const firstX = pad;
  return `${line} L${lastX},${baseY} L${firstX},${baseY} Z`;
}

function DonutChart({ percent, size = 100, color = "#22d3ee" }) {
  const r = 38;
  const c = 2 * Math.PI * r;
  const offset = c - (percent / 100) * c;
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className="ra-chart">
      <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(51,65,85,0.8)" strokeWidth="10" />
      <circle
        cx="50"
        cy="50"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 50 50)"
        style={{ filter: `drop-shadow(0 0 8px ${color})` }}
      />
      <text x="50" y="54" textAnchor="middle" className="ra-donut-center" fontSize="16">
        {percent.toFixed(1)}%
      </text>
    </svg>
  );
}

function BreakdownBars({ rows, valueKey = "total_commission", emptyMessage = "No data.", currency = "INR" }) {
  if (!rows?.length) {
    return <p className="ra-empty">{emptyMessage}</p>;
  }
  const max = Math.max(...rows.map((row) => row[valueKey] || 0), 1);
  return (
    <div className="ra-breakdown">
      {rows.map((row, index) => (
        <div key={`${row.label}-${index}`} className="ra-breakdown__row">
          <span className="ra-breakdown__label" title={row.label}>
            {row.label}
            {row.currency ? ` (${row.currency})` : ""}
          </span>
          <div className="ra-breakdown__track">
            <div
              className="ra-breakdown__fill"
              style={{ width: `${((row[valueKey] || 0) / max) * 100}%` }}
            />
          </div>
          <span className="ra-breakdown__value">
            {formatMoney(row[valueKey], row.currency || currency, { compact: true })}
          </span>
        </div>
      ))}
    </div>
  );
}

function KpiCard({ label, value, variant = "navy", hint, icon }) {
  return (
    <article className={`ra-kpi ra-kpi--${variant}`}>
      <div className="ra-kpi__top">
        <span className="ra-kpi__icon" aria-hidden="true">
          {icon}
        </span>
        <span className="ra-kpi__label">{label}</span>
      </div>
      <span className="ra-kpi__value">{value}</span>
      {hint && <span className="ra-kpi__hint">{hint}</span>}
    </article>
  );
}

function KpiStrip({ summary, sales, advanced, compact = false, fallbackCurrency = "INR" }) {
  const commissionCurrencies = activeCurrencyTotals(summary?.totals_by_currency);
  const salesCurrencies = activeCurrencyTotals(sales?.totals_by_currency);
  const commissionLabelCurrency =
    commissionCurrencies.length === 1 ? commissionCurrencies[0].currency : "";
  const salesLabelCurrency =
    salesCurrencies.length === 1 ? salesCurrencies[0].currency : "";
  const commissionCurrency =
    commissionLabelCurrency || fallbackCurrency || primaryCurrencyFromPayload(summary);
  const salesCurrency =
    salesLabelCurrency || fallbackCurrency || primaryCurrencyFromPayload(sales);
  const commissionTotal = formatDashboardAmount(
    summary?.totals_by_currency,
    summary?.total_commission,
    commissionCurrency,
    { compact }
  );
  const salesTotal = formatDashboardAmount(
    sales?.totals_by_currency,
    sales?.total_sales,
    salesCurrency,
    { compact }
  );

  return (
    <div className="ra-kpi-strip">
      <KpiCard
        variant="navy"
        icon="💰"
        label={`Total commission (${commissionCurrency})`}
        value={commissionTotal}
        hint={
          summary?.payout_record_count != null
            ? `${summary.payout_record_count} payout record${
                summary.payout_record_count === 1 ? "" : "s"
              } (includes manager splits)`
            : `${summary?.total_count ?? 0} payout records`
        }
      />
      <KpiCard
        variant="blue"
        icon="📈"
        label={`Total sales (${salesCurrency})`}
        value={salesTotal}
        hint="Order revenue in selected period"
      />
      <KpiCard
        variant="teal"
        icon="👥"
        label="Active reps"
        value={summary?.active_reps_count ?? "—"}
        hint="With commission in period"
      />
      <KpiCard
        variant="amber"
        icon="🎯"
        label="Avg attainment"
        value={
          advanced?.avg_attainment_pct != null ? `${advanced.avg_attainment_pct}%` : "—"
        }
        hint="Reps with personal targets"
      />
    </div>
  );
}

function AiInsightsPanel({ insights, loading, error, onRefresh }) {
  const renderList = (title, rows) => (
    <div className="ra-ai-insights__group">
      <h5>{title}</h5>
      {rows?.length ? (
        <ul>
          {rows.map((row, index) => (
            <li key={index}>{row}</li>
          ))}
        </ul>
      ) : (
        <p>No AI notes yet.</p>
      )}
    </div>
  );

  return (
    <div className="ra-panel ra-panel--ai ra-span-full">
      <div className="ra-panel__head">
        <div>
          <h4 className="ra-panel__title">AI Dashboard Insights</h4>
          <p className="ra-panel__subtitle">
            Generated from aggregate dashboard data. Review before taking action.
          </p>
        </div>
        <button type="button" className="ra-btn ra-btn--glass" onClick={onRefresh} disabled={loading}>
          {loading ? "Thinking..." : "Refresh AI"}
        </button>
      </div>
      {error && <p className="ra-ai-insights__error">{error}</p>}
      {!insights && !error && !loading && (
        <p className="ra-empty">Click Refresh AI to generate executive insights.</p>
      )}
      {loading && !insights && <p className="ra-empty">Generating AI insights...</p>}
      {insights && (
        <div className="ra-ai-insights">
          {renderList("Executive summary", insights.executive_summary)}
          {renderList("Risks", insights.risks)}
          {renderList("Opportunities", insights.opportunities)}
          {renderList("Recommended actions", insights.recommended_actions)}
        </div>
      )}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div className="ra-section-label">
      <span className="ra-section-label__line" aria-hidden="true" />
      <h3 className="ra-section-label__text">{children}</h3>
      <span className="ra-section-label__line" aria-hidden="true" />
    </div>
  );
}

function attainmentLevel(pct) {
  if (pct == null) return "neutral";
  if (pct >= 100) return "success";
  if (pct >= 70) return "warn";
  return "low";
}

function QuotaAchievementChart({ rows, limit = 8, fallbackCurrency = "INR" }) {
  if (!rows?.length) {
    return <p className="ra-empty">No quota data — set personal targets in User Setup.</p>;
  }

  return (
    <div className="ra-quota-grid">
      {rows.slice(0, limit).map((row, index) => {
        const quota = row.quota || 0;
        const achievement = row.achievement || 0;
        const pct = row.attainment_pct;
        const ringPct = pct != null ? Math.min(pct, 100) : 0;
        const level = attainmentLevel(pct);
        const rowCurrency = row.currency || row.personal_currency || fallbackCurrency;

        return (
          <article
            key={`${row.employee_id}-${index}`}
            className={`ra-quota-card ra-quota-card--${level}`}
          >
            <div
              className="ra-quota-ring"
              style={{ "--ring-pct": ringPct }}
              aria-hidden="true"
            >
              <div className="ra-quota-ring__inner">
                <span className="ra-quota-ring__value">
                  {pct != null ? `${pct}%` : "—"}
                </span>
                <span className="ra-quota-ring__label">attainment</span>
              </div>
            </div>
            <h5 className="ra-quota-card__name" title={row.employee_name}>
              {row.employee_name}
            </h5>
            <div className="ra-quota-card__stats">
              <div className="ra-quota-stat">
                <span className="ra-quota-stat__label">Quota</span>
                <span className="ra-quota-stat__value">
                  {formatMoney(quota, rowCurrency, { compact: true })}
                </span>
              </div>
              <div className="ra-quota-stat ra-quota-stat--achieved">
                <span className="ra-quota-stat__label">Achieved</span>
                <span className="ra-quota-stat__value">
                  {formatMoney(achievement, rowCurrency, { compact: true })}
                </span>
              </div>
            </div>
            {pct != null && pct > 100 && (
              <span className="ra-quota-card__over">Over target</span>
            )}
          </article>
        );
      })}
    </div>
  );
}

function ReportsAnalytics({ compact = false }) {
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [error, setError] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [period, setPeriod] = useState("monthly");
  const [businessGroup, setBusinessGroup] = useState("all");
  const [viewMode, setViewMode] = useState("analytics");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [debouncedEmployeeSearch, setDebouncedEmployeeSearch] = useState("");
  const [summary, setSummary] = useState(null);
  const [sales, setSales] = useState(null);
  const [periodData, setPeriodData] = useState(null);
  const [earnings, setEarnings] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [leaderboardMeta, setLeaderboardMeta] = useState({ limited: false, count: null });
  const [advanced, setAdvanced] = useState(null);
  const [aiInsights, setAiInsights] = useState(null);
  const [aiInsightsLoading, setAiInsightsLoading] = useState(false);
  const [aiInsightsError, setAiInsightsError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedEmployeeSearch(employeeSearch), 300);
    return () => window.clearTimeout(timer);
  }, [employeeSearch]);

  const employeeTableQuery = useCallback(() => {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (businessGroup !== "all") params.append("business_group", businessGroup);
    const term = debouncedEmployeeSearch.trim();
    if (term) {
      params.set("q", term);
    } else {
      params.set("limit", "15");
    }
    return params.toString() ? `?${params.toString()}` : "";
  }, [startDate, endDate, businessGroup, debouncedEmployeeSearch]);

  const loadDashboard = useCallback(async () => {
    setLoadingInitial(true);
    setError("");
    setSummary(null);
    setSales(null);
    setPeriodData(null);
    setAdvanced(null);
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (businessGroup !== "all") params.append("business_group", businessGroup);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const periodQs = `${qs}${qs ? "&" : "?"}period=${period}`;

    try {
      const results = await Promise.allSettled([
        api.get(`reports/commission-summary/${qs}`),
        api.get(`reports/sales-performance/${qs}`),
        api.get(`reports/period-analytics/${periodQs}`),
        api.get(`reports/advanced-analytics/${qs}`),
      ]);
      const failed = results.filter((r) => r.status === "rejected");
      if (failed.length === results.length) {
        throw failed[0].reason;
      }
      if (results[0].status === "fulfilled") setSummary(results[0].value.data);
      if (results[1].status === "fulfilled") setSales(results[1].value.data);
      if (results[2].status === "fulfilled") setPeriodData(results[2].value.data);
      if (results[3].status === "fulfilled") {
        setAdvanced(results[3].value.data);
      }
      if (failed.length > 0) {
        setError(
          `${failed.length} report request(s) failed. Showing partial data. Log in if session expired.`
        );
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load analytics"));
    } finally {
      setLoadingInitial(false);
    }
  }, [startDate, endDate, period, businessGroup]);

  const loadAiInsights = useCallback(async () => {
    if (compact) return;
    setAiInsightsLoading(true);
    setAiInsightsError("");
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (businessGroup !== "all") params.append("business_group", businessGroup);
    const qs = params.toString() ? `?${params.toString()}` : "";
    try {
      const res = await api.get(`ai/dashboard-insights/${qs}`);
      setAiInsights(res.data);
    } catch (err) {
      setAiInsightsError(getApiErrorMessage(err, "AI insights are not available"));
    } finally {
      setAiInsightsLoading(false);
    }
  }, [startDate, endDate, businessGroup, compact]);

  const loadEmployeeTables = useCallback(async () => {
    const employeeQs = employeeTableQuery();
    try {
      const [earningsRes, leaderboardRes] = await Promise.all([
        api.get(`reports/employee-earnings/${employeeQs}`),
        api.get(`leaderboard/${employeeQs}`),
      ]);
      setEarnings(earningsRes.data);
      setLeaderboard(leaderboardRes.data.results || []);
      setLeaderboardMeta({
        limited: Boolean(leaderboardRes.data.limited),
        count: leaderboardRes.data.count ?? null,
      });
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to refresh employee tables"));
    }
  }, [employeeTableQuery]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  // Employee search only refreshes the tables, never the full dashboard.
  useEffect(() => {
    loadEmployeeTables();
  }, [loadEmployeeTables]);

  const handleRefresh = () => {
    loadDashboard();
    loadEmployeeTables();
    loadAiInsights();
  };

  const chartHeight = compact ? 96 : 140;
  const quotaLimit = compact ? 4 : 8;
  const sparkCount = compact ? 8 : 12;

  const periodSeries = (periodData?.data || []).map((d) => d.total || 0);
  const periodHasValues = periodSeries.some((value) => value > 0);
  const periodCurrencies = activeCurrencyTotals(periodData?.totals_by_currency);
  const trendCurrency =
    periodCurrencies.length === 1
      ? periodCurrencies[0].currency
      : "";
  const trendScope =
    businessGroup === "all" ? "All business groups" : businessGroupLabel(businessGroup);
  const selectedBusinessCurrency =
    businessGroup === "all" ? "" : currencyForBusinessGroup(businessGroup, "");
  const dashboardFallbackCurrency =
    selectedBusinessCurrency || primaryCurrencyFromPayload(summary);
  const periodLabels = {
    monthly: "Monthly",
    quarterly: "Quarterly",
    annual: "Annual",
  };
  const topEarners = summary?.top_earners || [];
  const salesRows = (sales?.sales_data || []).slice(0, compact ? 6 : 8);
  const maxSales = Math.max(...salesRows.map((r) => r.total_sales || 0), 1);
  const maxPeriod = Math.max(...periodSeries, 1);

  const topShare =
    summary?.total_commission > 0 && topEarners[0]
      ? (parseFloat(topEarners[0].total) / parseFloat(summary.total_commission)) * 100
      : 0;

  const tableRows =
    viewMode === "reporting"
      ? earnings?.earnings || []
      : leaderboard.length
        ? leaderboard
        : topEarners.slice(0, 15);

  const exportCsv = () => {
    const cell = (value) => {
      const text = value == null ? "" : String(value);
      const safe = /^[=+\-@]/.test(text) ? `'${text}` : text;
      return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
    };
    const line = (...values) => `${values.map(cell).join(",")}\n`;

    let csv = "";
    csv += line("Performance overview export");
    csv += line("Date range", `${startDate || "All"} to ${endDate || "All"}`);
    csv += line("Business group", trendScope);
    csv += line("Period", periodLabels[period] || period);
    if (debouncedEmployeeSearch.trim()) {
      csv += line("Employee search", debouncedEmployeeSearch.trim());
    }
    csv += "\n";

    csv += line("Summary");
    csv += line("Total commission", summary?.total_commission || 0);
    csv += line("Payout records", summary?.payout_record_count ?? summary?.total_count ?? 0);
    csv += line("Total sales", sales?.total_sales || 0);
    csv += line("Active reps", summary?.active_reps_count ?? "");
    if (advanced?.avg_attainment_pct != null) {
      csv += line("Avg attainment %", advanced.avg_attainment_pct);
    }
    csv += "\n";

    csv += line(viewMode === "reporting" ? "All earnings" : "Leaderboard");
    csv += line("Name", "Email / ID", "Territory", "Amount", "Currency", "Count");
    tableRows.forEach((row) => {
      csv += line(
        row.employee_name || row.employee__name || row.employee_id || "",
        row.employee_email || row.employee__email || row.employee_id || "",
        row.territory || "",
        row.total_commission ?? row.total ?? row.total_earnings ?? row.total_sales ?? 0,
        row.currency || row.personal_currency || primaryCurrencyFromPayload(summary) || "",
        row.deal_count ?? row.count ?? row.commission_count ?? row.order_count ?? ""
      );
    });
    csv += "\n";

    if ((periodData?.data || []).length) {
      csv += line("Period breakdown");
      csv += line("Period", "Commission", "Count");
      periodData.data.forEach((row) => {
        csv += line(row.period, row.total, row.count);
      });
    }

    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `performance-overview-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const tableLimited =
    viewMode === "reporting"
      ? Boolean(earnings?.limited)
      : leaderboardMeta.limited && !debouncedEmployeeSearch.trim();

  const tableTotalCount =
    viewMode === "reporting" ? earnings?.count : leaderboardMeta.count;

  return (
    <div className={`ra-root${compact ? " ra-root--compact" : ""}`}>
      <header className="ra-header">
        <div className="ra-command-bar">
          <div className="ra-command-bar__glow" aria-hidden="true" />
          <div className="ra-command-bar__main">
            <div className="ra-command-bar__brand">
              <span className="ra-command-bar__eyebrow">Incentra · Command center</span>
              <h1 className="ra-command-bar__title">Performance overview</h1>
            </div>
            <div className="ra-command-bar__actions">
              <button
                type="button"
                className="ra-btn ra-btn--accent"
                onClick={handleRefresh}
                disabled={loadingInitial}
              >
                {loadingInitial ? "Loading…" : "Refresh"}
              </button>
              <button
                type="button"
                className="ra-btn ra-btn--glass"
                onClick={exportCsv}
                disabled={!summary}
              >
                Export
              </button>
            </div>
          </div>
        </div>

        <div className="ra-filter-toolbar">
          <label className="ra-filter-field ra-filter-field--view">
            <span className="ra-filter-field__label">View</span>
            <select value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
              <option value="analytics">Leaderboard</option>
              <option value="reporting">All earnings</option>
            </select>
          </label>
          <label className="ra-filter-field ra-filter-field--period">
            <span className="ra-filter-field__label">Period</span>
            <select value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="annual">Annual</option>
            </select>
          </label>
          <label className="ra-filter-field ra-filter-field--business">
            <span className="ra-filter-field__label">Business group</span>
            <select value={businessGroup} onChange={(e) => setBusinessGroup(e.target.value)}>
              <option value="all">All groups</option>
              {BUSINESS_GROUP_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="ra-filter-field ra-filter-field--date">
            <span className="ra-filter-field__label">From</span>
            <input
              type="date"
              value={startDate}
              max={endDate || undefined}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </label>
          <label className="ra-filter-field ra-filter-field--date">
            <span className="ra-filter-field__label">To</span>
            <input
              type="date"
              value={endDate}
              min={startDate || undefined}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </label>
        </div>
      </header>

      {error && <div className="ra-error">{error}</div>}

      {loadingInitial && !summary ? (
        <div className="ra-loading">
          <span className="ra-loading__pulse" aria-hidden="true" />
          Loading analytics…
        </div>
      ) : (
        <div className="ra-body">
          <KpiStrip
            summary={summary}
            sales={sales}
            advanced={advanced}
            compact={compact}
            fallbackCurrency={dashboardFallbackCurrency}
          />

          {!compact && (
            <AiInsightsPanel
              insights={aiInsights}
              loading={aiInsightsLoading}
              error={aiInsightsError}
              onRefresh={loadAiInsights}
            />
          )}

          {!compact && <SectionLabel>Trends & distribution</SectionLabel>}

          <div className="ra-grid">
            <div className={`ra-panel ra-panel--accent ${compact ? "ra-span-12" : "ra-span-8"}`}>
              <div className="ra-panel__head">
                <h4 className="ra-panel__title">Commission trend</h4>
                <span className="ra-panel__chip">
                  {periodLabels[period] || period}
                  {` · ${trendScope}`}
                  {trendCurrency ? ` · ${trendCurrency}` : ""}
                </span>
              </div>
              {periodHasValues ? (
                <>
                  <svg
                    viewBox={`0 0 400 ${chartHeight}`}
                    className="ra-chart"
                    preserveAspectRatio="xMidYMid meet"
                  >
                    <g className="ra-chart__grid">
                      {[0, 1, 2].map((i) => (
                        <line
                          key={i}
                          x1="12"
                          x2="388"
                          y1={16 + i * ((chartHeight - 32) / 2)}
                          y2={16 + i * ((chartHeight - 32) / 2)}
                        />
                      ))}
                    </g>
                    <path
                      className="ra-chart__area"
                      fill="url(#trendGrad)"
                      d={buildAreaPath(periodSeries, 400, chartHeight)}
                    />
                    <defs>
                      <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#0176d3" stopOpacity="0.35" />
                        <stop offset="100%" stopColor="#0176d3" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <path
                      className="ra-chart__line ra-chart__line--primary"
                      d={buildLinePath(periodSeries, 400, chartHeight)}
                    />
                    {periodSeries.map((v, i) => {
                      const x = 12 + (i / Math.max(periodSeries.length - 1, 1)) * 376;
                      const y = chartHeight - 12 - (v / maxPeriod) * (chartHeight - 28);
                      return (
                        <circle
                          key={i}
                          cx={x}
                          cy={y}
                          r="3"
                          className="ra-chart__dot ra-chart__dot--primary"
                        />
                      );
                    })}
                  </svg>
                  <div className="ra-legend">
                    <span className="ra-legend__primary">
                      {trendCurrency
                        ? `Commission totals (${trendCurrency})`
                        : "Commission totals by period"}
                    </span>
                  </div>
                </>
              ) : (
                <p className="ra-empty">
                  No commission trend data for this period. Adjust the date filters or upload AUD orders.
                </p>
              )}
            </div>

            {!compact && (
              <div className="ra-panel ra-panel--donut ra-span-4">
                <div className="ra-panel__head">
                  <h4 className="ra-panel__title">Payout concentration</h4>
                </div>
                <div className="ra-donut-wrap">
                  <DonutChart percent={Math.min(topShare, 100)} color="#0176d3" size={compact ? 80 : 100} />
                  <p className="ra-donut-caption">
                    Share of total commission earned by your top performer
                  </p>
                </div>
              </div>
            )}

            <div className={`ra-panel ra-panel--warm ${compact ? "ra-span-6" : "ra-span-6"}`}>
              <div className="ra-panel__head">
                <h4 className="ra-panel__title">Sales by rep</h4>
              </div>
              {salesRows.length > 0 ? (
                <svg viewBox={`0 0 360 ${compact ? 88 : 120}`} className="ra-chart">
                  {salesRows.map((row, i) => {
                    const barH = ((row.total_sales || 0) / maxSales) * 90;
                    const x = 16 + i * 42;
                    const y = 110 - barH;
                    return (
                      <rect
                        key={i}
                        x={x}
                        y={y}
                        width="28"
                        height={barH}
                        rx="3"
                        className={i % 2 ? "ra-bar ra-bar--alt" : "ra-bar"}
                      />
                    );
                  })}
                </svg>
              ) : (
                <p style={{ color: "#64748b", fontSize: 13 }}>No sales data.</p>
              )}
            </div>

            <div className="ra-panel ra-panel--cool ra-span-6">
              <div className="ra-panel__head">
                <h4 className="ra-panel__title">Top earners</h4>
              </div>
              <div className="ra-spark-row">
                {topEarners.slice(0, sparkCount).map((e, i) => {
                  const max = topEarners[0]?.total || 1;
                  const h = Math.max(6, ((e.total || 0) / max) * (compact ? 36 : 48));
                  return (
                    <div
                      key={i}
                      className="ra-spark-bar"
                      style={{ height: `${h}px`, opacity: 0.5 + (i % 3) * 0.15 }}
                      title={e.employee__name || e.employee_id}
                    />
                  );
                })}
              </div>
              <div className="ra-legend">
                <span className="ra-legend__teal">Relative commission</span>
              </div>
            </div>
          </div>

          {!compact && <SectionLabel>Breakdown & growth</SectionLabel>}

          <div className="ra-grid ra-grid--breakdown">
            {!compact && (
              <div className="ra-panel ra-panel--metric ra-span-3">
                <div className="ra-panel__head">
                  <h4 className="ra-panel__title">Attainment</h4>
                </div>
                {advanced?.avg_attainment_pct != null ? (
                  <>
                    <p className="ra-panel__value ra-panel__value--accent">
                      {advanced.avg_attainment_pct}%
                    </p>
                    <p className="ra-panel__desc">
                      Average quota attainment across reps with targets
                    </p>
                  </>
                ) : (
                  <p className="ra-empty">Set personal targets in User Setup to track attainment.</p>
                )}
              </div>
            )}

            {!compact && (
              <>
                <div className="ra-panel ra-span-4">
                  <div className="ra-panel__head">
                    <h4 className="ra-panel__title">By territory</h4>
                  </div>
                  <BreakdownBars rows={advanced?.by_territory} />
                </div>

                <div className="ra-panel ra-panel--warm ra-span-5">
                  <div className="ra-panel__head">
                    <h4 className="ra-panel__title">By product</h4>
                  </div>
                  <BreakdownBars rows={advanced?.by_product} />
                </div>

                <div className="ra-panel ra-span-6">
                  <div className="ra-panel__head">
                    <h4 className="ra-panel__title">By position</h4>
                  </div>
                  <BreakdownBars rows={advanced?.by_position} />
                </div>

                <div className="ra-panel ra-panel--growth ra-span-6">
                  <div className="ra-panel__head">
                    <h4 className="ra-panel__title">Top growth reps</h4>
                  </div>
                  {(advanced?.top_growth_reps || []).length > 0 ? (
                    <div className="ra-table-wrap">
                      <table className="ra-table">
                        <thead>
                          <tr>
                            <th>Rep</th>
                            <th align="right">Current</th>
                            <th align="right">Previous</th>
                            <th align="right">Growth</th>
                          </tr>
                        </thead>
                        <tbody>
                          {advanced.top_growth_reps.map((row, idx) => (
                            <tr key={row.employee_id || row.employee_email || `growth-${idx}`}>
                              <td>{row.employee_name || row.employee_id || "—"}</td>
                              <td align="right">{formatMoney(row.current_commission, row.currency, { compact })}</td>
                              <td align="right">{formatMoney(row.previous_commission, row.currency, { compact })}</td>
                              <td align="right">
                                <span
                                  className={`ra-growth-badge ${
                                    row.growth_pct >= 0
                                      ? "ra-growth-badge--up"
                                      : "ra-growth-badge--down"
                                  }`}
                                >
                                  {row.growth_pct >= 0 ? "+" : ""}
                                  {row.growth_pct}%
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="ra-empty">Not enough commission history for growth comparison.</p>
                  )}
                </div>
              </>
            )}

            <div className="ra-panel ra-panel--quota ra-span-full">
              <div className="ra-panel__head ra-panel__head--stacked">
                <div>
                  <h4 className="ra-panel__title">Quota vs achievement</h4>
                  <p className="ra-panel__subtitle">
                    Personal targets from User Setup compared to order sales in the selected period
                  </p>
                </div>
              </div>
              <QuotaAchievementChart
                rows={advanced?.quota_vs_achievement}
                limit={quotaLimit}
                fallbackCurrency={
                  selectedBusinessCurrency || primaryCurrencyFromPayload(sales)
                }
              />
            </div>
          </div>

          <SectionLabel>Team performance</SectionLabel>

          <div className="ra-panel ra-panel--table ra-span-12">
            <div className="ra-panel__head">
              <h4 className="ra-panel__title">
                {viewMode === "reporting" ? "All earnings" : "Leaderboard"}
              </h4>
              <label className="ra-employee-search">
                <span className="ra-employee-search__label">Employee search</span>
                <input
                  type="search"
                  value={employeeSearch}
                  onChange={(e) => setEmployeeSearch(e.target.value)}
                  placeholder="Name, email, or employee ID…"
                />
              </label>
            </div>
            {tableLimited && (
              <p className="ra-list-hint">
                Showing 15 of {tableTotalCount ?? "many"} employees. Search to find others.
              </p>
            )}
            <div className="ra-table-wrap">
              <table className="ra-table">
                <thead>
                  <tr>
                    {viewMode === "analytics" && leaderboard.length > 0 && <th>Rank</th>}
                    <th>Name</th>
                    <th>Email / ID</th>
                    {viewMode === "analytics" && leaderboard.length > 0 && <th>Territory</th>}
                    <th align="right">Amount</th>
                    <th align="right">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.length === 0 ? (
                    <tr>
                      <td colSpan={viewMode === "analytics" && leaderboard.length > 0 ? 6 : 4} style={{ color: "#64748b" }}>
                        No data — adjust dates and refresh.
                      </td>
                    </tr>
                  ) : (
                    tableRows.map((row, idx) => (
                      <tr
                        key={
                          row.employee_id ||
                          row.employee_email ||
                          row.employee__email ||
                          `row-${idx}`
                        }
                      >
                        {viewMode === "analytics" && leaderboard.length > 0 && (
                          <td>
                            <span className="ra-rank">{row.rank ?? idx + 1}</span>
                          </td>
                        )}
                        <td>
                          {row.employee_name || row.employee__name || row.employee_id || "—"}
                        </td>
                        <td>{row.employee_email || row.employee__email || row.employee_id || "—"}</td>
                        {viewMode === "analytics" && leaderboard.length > 0 && (
                          <td>{row.territory || "—"}</td>
                        )}
                        <td align="right">
                          {formatMoney(
                            row.total_commission || row.total || row.total_earnings || row.total_sales,
                            row.currency || row.personal_currency || primaryCurrencyFromPayload(summary),
                            { compact }
                          )}
                        </td>
                        <td align="right">
                          {row.deal_count || row.count || row.commission_count || row.order_count || "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {viewMode === "analytics" && (periodData?.data || []).length > 0 && !compact && (
              <div className="ra-subtable">
                <h4 className="ra-panel__title ra-subtable__title">Period breakdown</h4>
                <div className="ra-table-wrap">
                  <table className="ra-table">
                    <thead>
                      <tr>
                        <th>Period</th>
                        <th align="right">Commission</th>
                        <th align="right">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {periodData.data.map((row, idx) => (
                        <tr key={row.period || `period-${idx}`}>
                          <td>{row.period}</td>
                          <td align="right">
                            {formatMoneyList(row.totals_by_currency, "total", { compact }) ||
                              formatMoney(row.total, row.currency || trendCurrency, { compact })}
                          </td>
                          <td align="right">{row.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReportsAnalytics;
