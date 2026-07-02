import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../api";
import SearchBar from "../Components/SearchBar";
import PageHeader from "../Components/PageHeader";
import StatusPill from "../Components/StatusPill";
import {
  formatDashboardAmount,
  formatMoney,
  formatMoneyList,
  normalizeCurrency,
  primaryCurrencyFromPayload,
} from "../utils/currency";
import "./commissions.css";

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function parseCommissionRows(data) {
  if (Array.isArray(data)) return data;
  return data?.results || [];
}

function commissionTotalsByCurrency(rows) {
  const buckets = {};
  rows.forEach((row) => {
    const currency = normalizeCurrency(row.currency);
    buckets[currency] = (buckets[currency] || 0) + parseFloat(row.commission_amount || 0);
  });
  return Object.entries(buckets)
    .map(([currency, total]) => ({ currency, total }))
    .filter((row) => row.total > 0)
    .sort((a, b) => a.currency.localeCompare(b.currency));
}

function Commissions() {
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [canManagePayroll, setCanManagePayroll] = useState(false);

  const [activeTab, setActiveTab] = useState("commissions");
  const [reportType, setReportType] = useState("commission-summary");
  const [reportData, setReportData] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [period, setPeriod] = useState("monthly");
  const [statusFilter, setStatusFilter] = useState("all");
  const [actionMessage, setActionMessage] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const fetchUserProfile = useCallback(async () => {
    try {
      const response = await api.get("user-profile/");
      const admin = Boolean(response.data.is_admin);
      const finance = Boolean(response.data.is_finance);
      const manager = Boolean(response.data.is_manager);
      setIsAdmin(admin);
      setCanManagePayroll(admin || finance || manager);
    } catch {
      setIsAdmin(false);
      setCanManagePayroll(false);
    }
  }, []);

  const fetchCommissions = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.append("status", statusFilter);
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      const qs = params.toString();
      const response = await api.get(qs ? `commissions/?${qs}` : "commissions/");
      setCommissions(parseCommissionRows(response.data));
    } catch (err) {
      setCommissions([]);
      setLoadError(err.response?.data?.detail || "Failed to load commissions.");
    } finally {
      setLoading(false);
    }
  }, [endDate, startDate, statusFilter]);

  const fetchReport = useCallback(async () => {
    setReportLoading(true);
    setReportError("");
    try {
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      if (period && reportType === "period-analytics") params.append("period", period);

      const routes = {
        "commission-summary": "reports/commission-summary/",
        "sales-performance": "reports/sales-performance/",
        "employee-earnings": "reports/employee-earnings/",
        "period-analytics": "reports/period-analytics/",
      };
      const url = `${routes[reportType] || routes["commission-summary"]}?${params.toString()}`;
      const response = await api.get(url);
      setReportData(response.data);
    } catch (err) {
      setReportError(err.response?.data?.detail || err.message || "Failed to load report.");
      setReportData(null);
    } finally {
      setReportLoading(false);
    }
  }, [endDate, period, reportType, startDate]);

  useEffect(() => {
    fetchUserProfile();
  }, [fetchUserProfile]);

  useEffect(() => {
    if (activeTab === "commissions") {
      fetchCommissions();
    }
  }, [activeTab, fetchCommissions]);

  useEffect(() => {
    if (activeTab === "reports") {
      fetchReport();
    }
  }, [activeTab, fetchReport]);

  const handleApproveCalculated = async () => {
    if (!startDate || !endDate) {
      setActionMessage("Set start and end dates to approve commissions for a period.");
      return;
    }
    setActionLoading(true);
    setActionMessage("");
    try {
      const response = await api.post("commissions/approve/", {
        start_date: startDate,
        end_date: endDate,
      });
      setActionMessage(`Approved ${response.data.approved} commission(s).`);
      fetchCommissions();
    } catch (err) {
      setActionMessage(err.response?.data?.error || "Failed to approve commissions.");
    } finally {
      setActionLoading(false);
    }
  };

  const handlePayrollExport = async () => {
    setActionLoading(true);
    setActionMessage("");
    try {
      const params = new URLSearchParams({ status: "approved" });
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      const response = await api.get(`commissions/export/?${params.toString()}`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `payroll-commissions-${new Date().toISOString().split("T")[0]}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      setActionMessage("Payroll CSV downloaded.");
    } catch {
      setActionMessage("Failed to export payroll CSV.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRecalculate = async () => {
    if (!startDate || !endDate) {
      setActionMessage("Set start and end dates to recalculate.");
      return;
    }
    const force = window.confirm(
      "Recalculate all orders in this period?\n\nOK = replace approved commissions too.\nCancel = skip orders that are already approved."
    );
    setActionLoading(true);
    setActionMessage("");
    try {
      const response = await api.post("commissions/recalculate/", {
        start_date: startDate,
        end_date: endDate,
        force,
      });
      const s = response.data;
      setActionMessage(
        `Recalculated ${s.processed} order(s). Skipped (approved): ${s.skipped_approved}. Failed: ${s.failed}.`
      );
      fetchCommissions();
    } catch (err) {
      setActionMessage(err.response?.data?.error || "Recalculate failed.");
    } finally {
      setActionLoading(false);
    }
  };

  const exportToCSV = () => {
    if (!reportData) return;
    let csv = "";
    if (reportType === "commission-summary" && reportData.top_earners) {
      csv = "Name,Email,Total Commission,Count\n";
      reportData.top_earners.forEach((item) => {
        csv += `"${item.employee__name || item.employee_id}","${item.employee__email || ""}",${item.total},${item.count}\n`;
      });
    } else if (reportType === "sales-performance" && reportData.sales_data) {
      csv = "Employee ID,Position,Total Sales,Order Count\n";
      reportData.sales_data.forEach((item) => {
        csv += `"${item.employee_id}","${item.position_name || ""}",${item.total_sales},${item.order_count}\n`;
      });
    } else if (reportType === "employee-earnings" && reportData.earnings) {
      csv = "Name,Email,Total Earnings,Commission Count\n";
      reportData.earnings.forEach((item) => {
        csv += `"${item.employee__name || ""}","${item.employee__email || ""}",${item.total_earnings},${item.commission_count}\n`;
      });
    }
    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${reportType}-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const filteredCommissions = useMemo(() => {
    const searchLower = searchTerm.trim().toLowerCase();
    if (!searchLower) return commissions;
    return commissions.filter((commission) => {
      return (
        (commission.employee_name && commission.employee_name.toLowerCase().includes(searchLower)) ||
        (commission.employee_email && commission.employee_email.toLowerCase().includes(searchLower)) ||
        (commission.employee_id && String(commission.employee_id).toLowerCase().includes(searchLower)) ||
        (commission.order_id && String(commission.order_id).toLowerCase().includes(searchLower)) ||
        (commission.plan_name && commission.plan_name.toLowerCase().includes(searchLower))
      );
    });
  }, [commissions, searchTerm]);

  const totalsByCurrency = useMemo(
    () => commissionTotalsByCurrency(commissions),
    [commissions]
  );
  const primaryCurrency = totalsByCurrency.length === 1 ? totalsByCurrency[0].currency : "USD";
  const totalAmountLabel = formatMoneyList(totalsByCurrency, "total") || formatMoney(0, primaryCurrency);
  const avgAmountLabel = useMemo(() => {
    if (!commissions.length) return formatMoney(0, primaryCurrency);
    if (totalsByCurrency.length === 1) {
      return formatMoney(
        totalsByCurrency[0].total / commissions.length,
        totalsByCurrency[0].currency
      );
    }
    return "Multiple currencies";
  }, [commissions.length, primaryCurrency, totalsByCurrency]);

  const reportCurrency = primaryCurrencyFromPayload(reportData, primaryCurrency);

  return (
    <div className="commissions-page">
      <PageHeader
        badge="Payroll"
        title="Commissions"
        subtitle={
          isAdmin
            ? "Review payout records, approve calculated commissions, and export payroll."
            : "View your commission records and payout status."
        }
      />

      <div className="tabs">
        <button
          type="button"
          onClick={() => setActiveTab("commissions")}
          className={`tab${activeTab === "commissions" ? " tab--active" : ""}`}
        >
          Commission records
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("reports")}
          className={`tab${activeTab === "reports" ? " tab--active" : ""}`}
        >
          Reports
        </button>
      </div>

      {activeTab === "commissions" && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card__icon">💼</div>
              <div>
                <p className="stat-card__label">Payout records</p>
                <p className="stat-card__value">{commissions.length}</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__icon">💵</div>
              <div>
                <p className="stat-card__label">Total amount</p>
                <p className="stat-card__value">{totalAmountLabel}</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__icon">📊</div>
              <div>
                <p className="stat-card__label">Average payout</p>
                <p className="stat-card__value">{avgAmountLabel}</p>
              </div>
            </div>
          </div>

          <div className="panel commissions-toolbar">
            <div className="commissions-toolbar__section">
              <span className="commissions-toolbar__label">Filters</span>
              <SearchBar
                className="commissions-filter-search"
                placeholder="Search rep, order, plan…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <select
                className="input commissions-filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Commission status"
              >
                <option value="all">All statuses</option>
                <option value="calculated">Calculated</option>
                <option value="manager_approved">Manager approved</option>
                <option value="approved">Finance approved</option>
                <option value="paid">Paid</option>
              </select>
              <input
                type="date"
                className="input commissions-filter-date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                aria-label="Period start"
              />
              <input
                type="date"
                className="input commissions-filter-date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                aria-label="Period end"
              />
              <button type="button" className="btn-primary" onClick={fetchCommissions} disabled={loading}>
                {loading ? "Loading…" : "Refresh"}
              </button>
            </div>

            {canManagePayroll && (
              <div className="commissions-toolbar__section">
                <span className="commissions-toolbar__label">Actions</span>
                {isAdmin && (
                  <>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleApproveCalculated}
                      disabled={actionLoading}
                    >
                      Approve calculated
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleRecalculate}
                      disabled={actionLoading}
                    >
                      Recalculate period
                    </button>
                  </>
                )}
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handlePayrollExport}
                  disabled={actionLoading}
                >
                  Export payroll CSV
                </button>
              </div>
            )}

            {actionMessage && <p className="commissions-banner">{actionMessage}</p>}
          </div>

          {!isAdmin && !canManagePayroll && (
            <div className="banner commissions-banner--info">
              <strong>Personal view:</strong> You&apos;re viewing your commissions only.
            </div>
          )}

          <div className="panel commissions-records">
            <div className="commissions-records__header">
              <h2 className="commissions-records__title">Payout records</h2>
              <span className="commissions-records__count">
                {filteredCommissions.length} shown
              </span>
            </div>
            {totalsByCurrency.length > 1 && (
              <p className="commissions-records__hint">
                Totals span multiple currencies: {formatMoneyList(totalsByCurrency, "total")}
              </p>
            )}

            <div className="commissions-table-wrap">
              <table className="commissions-table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Email</th>
                    <th>Employee ID</th>
                    <th>Order / period</th>
                    <th>Plan</th>
                    <th className="commissions-table__num">Amount</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={8} className="commissions-table__state">
                        <div className="commissions-table__state-icon">⏳</div>
                        <p className="commissions-table__state-title">Loading commissions…</p>
                      </td>
                    </tr>
                  ) : loadError ? (
                    <tr>
                      <td colSpan={8} className="commissions-table__state">
                        <p className="commissions-table__state-title">{loadError}</p>
                      </td>
                    </tr>
                  ) : filteredCommissions.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="commissions-table__state">
                        <div className="commissions-table__state-icon">📊</div>
                        <p className="commissions-table__state-title">
                          {searchTerm ? "No matching commissions found" : "No commissions yet"}
                        </p>
                        <p className="commissions-table__state-hint">
                          Mark orders Success in the order queue to generate commissions.
                        </p>
                      </td>
                    </tr>
                  ) : (
                    filteredCommissions.map((commission) => (
                      <tr key={commission.id}>
                        <td>
                          <span className="commissions-table__employee">
                            {commission.employee_name || "Unknown"}
                          </span>
                        </td>
                        <td>
                          <span className="commissions-table__email">
                            {commission.employee_email || "—"}
                          </span>
                        </td>
                        <td>
                          <span className="commissions-table__emp-id">
                            {commission.employee_id || "—"}
                          </span>
                        </td>
                        <td>
                          <span className="commissions-table__order-id">
                            {commission.order_id || "—"}
                          </span>
                        </td>
                        <td>{commission.plan_name || "—"}</td>
                        <td className="commissions-table__num">
                          <span className="commissions-table__amount">
                            {formatMoney(commission.commission_amount, commission.currency)}
                          </span>
                        </td>
                        <td>
                          <div className="commissions-table__status">
                            <StatusPill status={commission.status} compact />
                          </div>
                        </td>
                        <td>
                          <span className="commissions-table__date">
                            {formatDate(commission.order_date || commission.period_start)}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {activeTab === "reports" && (
        <>
          <div className="panel commissions-toolbar">
            <div className="commissions-toolbar__section">
              <span className="commissions-toolbar__label">Report</span>
              <select
                className="input commissions-filter-status"
                value={reportType}
                onChange={(e) => setReportType(e.target.value)}
              >
                <option value="commission-summary">Commission summary</option>
                <option value="sales-performance">Sales performance</option>
                <option value="employee-earnings">Employee earnings</option>
                <option value="period-analytics">Period analytics</option>
              </select>
              {reportType === "period-analytics" && (
                <select
                  className="input commissions-filter-status"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="annual">Annual</option>
                </select>
              )}
              <input
                type="date"
                className="input commissions-filter-date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <input
                type="date"
                className="input commissions-filter-date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
              <button type="button" className="btn-primary" onClick={fetchReport} disabled={reportLoading}>
                {reportLoading ? "Loading…" : "Apply"}
              </button>
              {reportData && (
                <button type="button" className="btn-secondary" onClick={exportToCSV}>
                  Export CSV
                </button>
              )}
            </div>
          </div>

          {reportError && <div className="banner">{reportError}</div>}

          {reportLoading ? (
            <div className="panel commissions-table__state">Loading report…</div>
          ) : reportData ? (
            <>
              {reportType === "commission-summary" && (
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-card__icon">💰</div>
                    <div>
                      <p className="stat-card__label">Total commission</p>
                      <p className="stat-card__value">
                        {formatDashboardAmount(
                          reportData.totals_by_currency,
                          reportData.total_commission,
                          reportCurrency
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-card__icon">📈</div>
                    <div>
                      <p className="stat-card__label">Payout records</p>
                      <p className="stat-card__value">{reportData.total_count || 0}</p>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-card__icon">👥</div>
                    <div>
                      <p className="stat-card__label">Active reps</p>
                      <p className="stat-card__value">{reportData.active_reps_count ?? "—"}</p>
                    </div>
                  </div>
                </div>
              )}

              <div className="panel commissions-records">
                <div className="commissions-records__header">
                  <h2 className="commissions-records__title">
                    {reportType.replace(/-/g, " ")}
                  </h2>
                </div>
                <div className="commissions-table-wrap">
                  <table className="commissions-table">
                    <thead>
                      <tr>
                        {reportType === "commission-summary" && (
                          <>
                            <th>Employee</th>
                            <th>Email</th>
                            <th className="commissions-table__num">Total</th>
                            <th className="commissions-table__num">Count</th>
                          </>
                        )}
                        {reportType === "sales-performance" && (
                          <>
                            <th>Employee ID</th>
                            <th>Position</th>
                            <th className="commissions-table__num">Sales</th>
                            <th className="commissions-table__num">Orders</th>
                          </>
                        )}
                        {reportType === "employee-earnings" && (
                          <>
                            <th>Employee</th>
                            <th>Email</th>
                            <th className="commissions-table__num">Earnings</th>
                            <th className="commissions-table__num">Count</th>
                          </>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {reportType === "commission-summary" &&
                        (reportData.top_earners?.length ? (
                          reportData.top_earners.map((item, idx) => (
                            <tr key={idx}>
                              <td>{item.employee__name || item.employee_id}</td>
                              <td>{item.employee__email || "—"}</td>
                              <td className="commissions-table__num">
                                {formatMoney(item.total, reportCurrency)}
                              </td>
                              <td className="commissions-table__num">{item.count}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={4} className="commissions-table__state">
                              No top earners for this period
                            </td>
                          </tr>
                        ))}
                      {reportType === "sales-performance" &&
                        (reportData.sales_data?.length ? (
                          reportData.sales_data.map((item, idx) => (
                            <tr key={idx}>
                              <td>{item.employee_id}</td>
                              <td>{item.position_name || "—"}</td>
                              <td className="commissions-table__num">
                                {formatDashboardAmount(
                                  reportData.totals_by_currency,
                                  item.total_sales,
                                  reportCurrency
                                )}
                              </td>
                              <td className="commissions-table__num">{item.order_count}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={4} className="commissions-table__state">
                              No sales data for this period
                            </td>
                          </tr>
                        ))}
                      {reportType === "employee-earnings" &&
                        (reportData.earnings?.length ? (
                          reportData.earnings.map((item, idx) => (
                            <tr key={idx}>
                              <td>{item.employee__name || "—"}</td>
                              <td>{item.employee__email || "—"}</td>
                              <td className="commissions-table__num">
                                {formatMoney(item.total_earnings, reportCurrency)}
                              </td>
                              <td className="commissions-table__num">{item.commission_count}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={4} className="commissions-table__state">
                              No earnings data for this period
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="panel commissions-table__state">
              <p className="commissions-table__state-title">No report data</p>
              <p className="commissions-table__state-hint">Choose filters and click Apply.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default Commissions;
