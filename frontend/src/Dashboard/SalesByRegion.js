import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import PageHeader from "../Components/PageHeader";
import PeriodFilter from "../Components/PeriodFilter";
import {
  formatDashboardAmount,
  formatMoney,
  primaryCurrencyFromPayload,
} from "../utils/currency";
import "./reportsAnalytics.css";
import "./salesByRegion.css";

function defaultPeriod() {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - 30);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

function matchesSearch(label, query) {
  if (!query) return true;
  return String(label || "")
    .toLowerCase()
    .includes(query.toLowerCase());
}

function BreakdownBars({ rows, emptyMessage = "No sales in this period." }) {
  if (!rows?.length) {
    return <p className="ra-empty">{emptyMessage}</p>;
  }
  const max = Math.max(...rows.map((row) => row.total_sales || 0), 1);
  return (
    <div className="ra-breakdown">
      {rows.map((row, index) => (
        <div key={`${row.label}-${row.currency}-${index}`} className="ra-breakdown__row">
          <span className="ra-breakdown__label" title={row.label}>
            {row.label}
            {row.currency ? ` (${row.currency})` : ""}
          </span>
          <div className="ra-breakdown__track">
            <div
              className="ra-breakdown__fill"
              style={{ width: `${((row.total_sales || 0) / max) * 100}%` }}
            />
          </div>
          <span className="ra-breakdown__value">
            {formatMoney(row.total_sales, row.currency || "INR", { compact: true })}
          </span>
        </div>
      ))}
    </div>
  );
}

function SalesByRegion() {
  const defaults = defaultPeriod();
  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);
  const [search, setSearch] = useState("");
  const [data, setData] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [accessChecked, setAccessChecked] = useState(false);

  useEffect(() => {
    api
      .get("user-profile/")
      .then((res) => setProfile(res.data))
      .catch(() => setProfile(null))
      .finally(() => setAccessChecked(true));
  }, []);

  const canView =
    Boolean(profile?.is_admin) ||
    Boolean(profile?.is_finance) ||
    Boolean(profile?.is_manager) ||
    ["admin", "administrator", "finance", "manager"].includes(
      String(profile?.role || "").toLowerCase()
    );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const res = await api.get("reports/sales-by-region/", { params });
      setData(res.data);
    } catch (err) {
      setData(null);
      setError(getApiErrorMessage(err, "Unable to load sales by region."));
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    if (accessChecked && canView) {
      load();
    }
  }, [accessChecked, canView, load]);

  const query = search.trim();

  const regionRows = useMemo(
    () => (data?.by_region || []).filter((row) => matchesSearch(row.label, query)),
    [data, query]
  );

  const territoryRows = useMemo(
    () => (data?.by_territory || []).filter((row) => matchesSearch(row.label, query)),
    [data, query]
  );

  const exportCsv = () => {
    if (!data) return;
    let csv = "Section,Label,Currency,Total Sales,Order Count,Pct of Total\n";
    regionRows.forEach((row) => {
      csv += `Region,"${row.label}",${row.currency || ""},${row.total_sales},${row.order_count},${row.pct_of_total || 0}\n`;
    });
    territoryRows.forEach((row) => {
      csv += `Territory,"${row.label}",${row.currency || ""},${row.total_sales},${row.order_count},${row.pct_of_total || 0}\n`;
    });
    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sales-by-region-${startDate || "all"}-${endDate || "all"}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (!accessChecked) {
    return <div className="sbr-root">Loading…</div>;
  }

  if (!canView) {
    return <Navigate to="/statement" replace />;
  }

  const currency = primaryCurrencyFromPayload(data) || "INR";
  const salesTotal = formatDashboardAmount(
    data?.totals_by_currency,
    data?.total_sales,
    currency,
    { compact: false }
  );

  return (
    <div className="sbr-root">
      <PageHeader
        badge="Sales analysis"
        title="Sales by region"
        subtitle="Distribution performance by Indian state (region) and territory."
      />

      <div className="panel sbr-filters">
        <PeriodFilter
          startDate={startDate}
          endDate={endDate}
          onStartChange={setStartDate}
          onEndChange={setEndDate}
          onSubmit={load}
          loading={loading}
          submitLabel="Apply"
        >
          <label className="sbr-search">
            <span>Search</span>
            <input
              className="input"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="State or territory…"
              aria-label="Search states or territories"
            />
          </label>
          <button
            type="button"
            className="btn-secondary"
            onClick={exportCsv}
            disabled={!data || loading}
          >
            Export CSV
          </button>
        </PeriodFilter>
        {query && (
          <p className="sbr-search-hint">
            Showing matches for “{query}” — {regionRows.length} state
            {regionRows.length === 1 ? "" : "s"}, {territoryRows.length} territor
            {territoryRows.length === 1 ? "y" : "ies"}.
          </p>
        )}
        {error && <p className="sbr-error">{error}</p>}
      </div>

      <div className="sbr-kpis">
        <article className="ra-kpi ra-kpi--navy">
          <div className="ra-kpi__top">
            <span className="ra-kpi__label">Total sales</span>
          </div>
          <span className="ra-kpi__value">{loading ? "…" : salesTotal}</span>
        </article>
        <article className="ra-kpi ra-kpi--teal">
          <div className="ra-kpi__top">
            <span className="ra-kpi__label">Orders</span>
          </div>
          <span className="ra-kpi__value">{loading ? "…" : data?.total_orders ?? 0}</span>
        </article>
        <article className="ra-kpi ra-kpi--warm">
          <div className="ra-kpi__top">
            <span className="ra-kpi__label">States with sales</span>
          </div>
          <span className="ra-kpi__value">{loading ? "…" : data?.region_count ?? 0}</span>
        </article>
      </div>

      <div className="sbr-grid">
        <div className="ra-panel">
          <div className="ra-panel__head">
            <h4 className="ra-panel__title">Sales by state (region)</h4>
          </div>
          {loading ? (
            <p className="ra-empty">Loading…</p>
          ) : (
            <BreakdownBars
              rows={regionRows}
              emptyMessage={
                query ? `No states match “${query}”.` : "No sales in this period."
              }
            />
          )}
        </div>
        <div className="ra-panel ra-panel--warm">
          <div className="ra-panel__head">
            <h4 className="ra-panel__title">Sales by territory</h4>
          </div>
          {loading ? (
            <p className="ra-empty">Loading…</p>
          ) : (
            <BreakdownBars
              rows={territoryRows}
              emptyMessage={
                query
                  ? `No territories match “${query}”.`
                  : "No territory-tagged sales."
              }
            />
          )}
        </div>
      </div>

      <div className="panel sbr-table-panel">
        <h3 className="sbr-table-title">Region detail</h3>
        <div className="sbr-table-wrap">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th>Region / state</th>
                <th>Currency</th>
                <th>Sales</th>
                <th>Orders</th>
                <th>% of total</th>
              </tr>
            </thead>
            <tbody>
              {!loading && regionRows.length === 0 && (
                <tr>
                  <td colSpan={5}>
                    {query
                      ? `No regions match “${query}”.`
                      : "No regional sales for this period. Set region on orders (e.g. Maharashtra)."}
                  </td>
                </tr>
              )}
              {regionRows.map((row, index) => (
                <tr key={`${row.label}-${row.currency}-${index}`}>
                  <td>{row.label}</td>
                  <td>{row.currency || "—"}</td>
                  <td>{formatMoney(row.total_sales, row.currency || currency)}</td>
                  <td>{row.order_count}</td>
                  <td>{row.pct_of_total != null ? `${row.pct_of_total}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default SalesByRegion;
