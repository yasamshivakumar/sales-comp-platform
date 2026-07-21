import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import DatePickerField from "../Components/DatePickerField";
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
    const combinedRows = (data.by_region_territory || []).filter(
      (row) => matchesSearch(row.region, query) || matchesSearch(row.territory, query)
    );
    let csv = "Region,Territory,Currency,Total Sales,Order Count,Pct of Total\n";
    if (combinedRows.length) {
      combinedRows.forEach((row) => {
        csv += `"${row.region}","${row.territory}",${row.currency || ""},${row.total_sales},${row.order_count},${row.pct_of_total || 0}\n`;
      });
    } else {
      // Older backend without the combined breakdown: fall back to region rows.
      regionRows.forEach((row) => {
        csv += `"${row.label}",,${row.currency || ""},${row.total_sales},${row.order_count},${row.pct_of_total || 0}\n`;
      });
    }
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
      <header className="sbr-hero">
        <div className="sbr-hero__glow" aria-hidden="true" />
        <div className="sbr-hero__content">
          <span className="sbr-hero__eyebrow">Distribution insights</span>
          <h1 className="sbr-hero__title">Sales insights</h1>
        </div>
      </header>

      <div className="sbr-filters">
        <div className="sbr-toolbar">
          <div className="sbr-toolbar__field">
            <DatePickerField
              id="sbr-start-date"
              label="From"
              value={startDate}
              onChange={setStartDate}
              maxDate={endDate || undefined}
              fullWidth
              size="small"
              className="sbr-date-field"
            />
          </div>
          <div className="sbr-toolbar__field">
            <DatePickerField
              id="sbr-end-date"
              label="To"
              value={endDate}
              onChange={setEndDate}
              minDate={startDate || undefined}
              fullWidth
              size="small"
              className="sbr-date-field"
            />
          </div>
          <div className="sbr-toolbar__field sbr-toolbar__field--search">
            <label className="sbr-toolbar__label" htmlFor="sbr-search">
              Search
            </label>
            <input
              id="sbr-search"
              type="search"
              className="sbr-search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Region…"
            />
          </div>
          <div className="sbr-toolbar__field sbr-toolbar__field--actions">
            <button
              type="button"
              className="btn-primary sbr-toolbar__btn"
              onClick={load}
              disabled={loading}
            >
              {loading ? "Loading…" : "Apply"}
            </button>
            <button
              type="button"
              className="btn-secondary sbr-toolbar__btn"
              onClick={exportCsv}
              disabled={!data || loading}
            >
              Export
            </button>
          </div>
        </div>
        {query && (
          <p className="sbr-search-hint">
            Showing matches for “{query}” — {regionRows.length} region
            {regionRows.length === 1 ? "" : "s"}, {territoryRows.length} territor
            {territoryRows.length === 1 ? "y" : "ies"}.
          </p>
        )}
        {error && <p className="sbr-error">{error}</p>}
      </div>

      <div className="sbr-kpis">
        <article className="sbr-kpi sbr-kpi--navy">
          <span className="sbr-kpi__label">Total sales</span>
          <span className="sbr-kpi__value">{loading ? "…" : salesTotal}</span>
        </article>
        <article className="sbr-kpi sbr-kpi--teal">
          <span className="sbr-kpi__label">Orders</span>
          <span className="sbr-kpi__value">{loading ? "…" : data?.total_orders ?? 0}</span>
        </article>
        <article className="sbr-kpi sbr-kpi--amber">
          <span className="sbr-kpi__label">Regions with sales</span>
          <span className="sbr-kpi__value">{loading ? "…" : data?.region_count ?? 0}</span>
        </article>
      </div>

      <div className="sbr-grid">
        <section className="sbr-card">
          <div className="sbr-card__head">
            <h2 className="sbr-card__title">By region</h2>
            <span className="sbr-card__meta">Geography</span>
          </div>
          {loading ? (
            <p className="ra-empty">Loading…</p>
          ) : (
            <BreakdownBars
              rows={regionRows}
              emptyMessage={
                query ? `No regions match “${query}”.` : "No sales in this period."
              }
            />
          )}
        </section>
        <section className="sbr-card sbr-card--warm">
          <div className="sbr-card__head">
            <h2 className="sbr-card__title">By territory</h2>
            <span className="sbr-card__meta">Zone</span>
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
        </section>
      </div>

      <section className="sbr-card sbr-card--table">
        <div className="sbr-card__head">
          <h2 className="sbr-card__title">Region detail</h2>
          <span className="sbr-card__meta">{regionRows.length} rows</span>
        </div>
        <div className="sbr-table-wrap">
          <table className="sbr-table">
            <thead>
              <tr>
                <th>Region</th>
                <th>Currency</th>
                <th>Sales</th>
                <th>Orders</th>
                <th>% of total</th>
              </tr>
            </thead>
            <tbody>
              {!loading && regionRows.length === 0 && (
                <tr>
                  <td colSpan={5} className="sbr-table__empty">
                    {query
                      ? `No regions match “${query}”.`
                      : "No regional sales for this period. Set region on orders (e.g. Maharashtra)."}
                  </td>
                </tr>
              )}
              {regionRows.map((row, index) => (
                <tr key={`${row.label}-${row.currency}-${index}`}>
                  <td className="sbr-table__name">{row.label}</td>
                  <td>{row.currency || "—"}</td>
                  <td>{formatMoney(row.total_sales, row.currency || currency)}</td>
                  <td>{row.order_count}</td>
                  <td>
                    <span className="sbr-pct">{row.pct_of_total != null ? `${row.pct_of_total}%` : "—"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default SalesByRegion;
