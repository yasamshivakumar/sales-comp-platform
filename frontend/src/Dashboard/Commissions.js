import { useState, useEffect } from "react";
import api from "../api";
import SearchBar from "../Components/SearchBar";
import PageHeader from "../Components/PageHeader";

function Commissions() {
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [userRole, setUserRole] = useState("Employee");
  const [isAdmin, setIsAdmin] = useState(false);
  const [canManagePayroll, setCanManagePayroll] = useState(false);

  // Reports state
  const [activeTab, setActiveTab] = useState("commissions"); // commissions, reports
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

  useEffect(() => {
    fetchUserProfile();
    fetchCommissions();
  }, []);

  useEffect(() => {
    if (activeTab === "reports") {
      fetchReport();
    }
  }, [reportType, period, activeTab]);

  const fetchUserProfile = async () => {
    try {
      const response = await api.get("user-profile/");
      setUserRole(response.data.role);
      const admin = Boolean(response.data.is_admin);
      const finance = Boolean(response.data.is_finance);
      setIsAdmin(admin);
      setCanManagePayroll(admin || finance);
    } catch (err) {
      setUserRole("Employee");
      setIsAdmin(false);
    }
  };

  const fetchCommissions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter === "calculated" || statusFilter === "approved") {
        params.append("status", statusFilter);
      }
      const qs = params.toString();
      const response = await api.get(qs ? `commissions/?${qs}` : "commissions/");
      setCommissions(response.data);
    } catch (err) {
      console.error("Failed to load commissions", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "commissions") {
      fetchCommissions();
    }
  }, [statusFilter]);

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
      setActionMessage(
        err.response?.data?.error || "Failed to approve commissions."
      );
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
    } catch (err) {
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
      setActionMessage(
        err.response?.data?.error || "Recalculate failed."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const fetchReport = async () => {
    setReportLoading(true);
    setReportError("");
    try {
      let url = "";
      const params = new URLSearchParams();

      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      if (period && reportType === "period-analytics") params.append("period", period);

      switch (reportType) {
        case "commission-summary":
          url = `reports/commission-summary/?${params.toString()}`;
          break;
        case "sales-performance":
          url = `reports/sales-performance/?${params.toString()}`;
          break;
        case "employee-earnings":
          url = `reports/employee-earnings/?${params.toString()}`;
          break;
        case "period-analytics":
          url = `reports/period-analytics/?${params.toString()}`;
          break;
        default:
          url = "reports/commission-summary/";
      }

      const response = await api.get(url);
      setReportData(response.data);
    } catch (err) {
      setReportError("Failed to load report: " + (err.response?.data?.detail || err.message));
      console.error(err);
    } finally {
      setReportLoading(false);
    }
  };

  const handleApplyFilter = () => {
    fetchReport();
  };

  const exportToCSV = () => {
    if (!reportData) return;

    let csv = "";
    let rows = [];

    if (reportType === "commission-summary" && reportData.top_earners) {
      csv = "Name,Email,Total Commission,Count\n";
      reportData.top_earners.forEach((item) => {
        csv += `"${item.employee__name || item.employee_id}","${item.employee__email || ''}",${item.total},${item.count}\n`;
      });
    } else if (reportType === "sales-performance" && reportData.sales_data) {
      csv = "Employee ID,Position,Total Sales,Order Count\n";
      reportData.sales_data.forEach((item) => {
        csv += `"${item.employee_id}","${item.position_name || ''}",${item.total_sales},${item.order_count}\n`;
      });
    } else if (reportType === "employee-earnings" && reportData.earnings) {
      csv = "Name,Email,Total Earnings,Commission Count\n";
      reportData.earnings.forEach((item) => {
        csv += `"${item.employee__name || ''}","${item.employee__email || ''}",${item.total_earnings},${item.commission_count}\n`;
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

  const filteredCommissions = commissions.filter((commission) => {
    const searchLower = searchTerm.toLowerCase();
    const matchesSearch =
      (commission.employee_name && commission.employee_name.toLowerCase().includes(searchLower)) ||
      (commission.employee_email && commission.employee_email.toLowerCase().includes(searchLower)) ||
      (commission.employee_id && commission.employee_id.toLowerCase().includes(searchLower));

    return matchesSearch;
  });

  const totalCommission = commissions.reduce(
    (sum, c) => sum + parseFloat(c.commission_amount || 0),
    0
  );

  const avgCommission = commissions.length > 0 ? totalCommission / commissions.length : 0;

  return (
    <div>
      <PageHeader
        badge="Analytics"
        title="Commissions & Reports"
        subtitle={
          isAdmin
            ? "Manage all employee commissions, earnings, and analytics."
            : "View your personal commissions and earnings."
        }
      />

      <div className="tabs">
        <button
          type="button"
          onClick={() => setActiveTab("commissions")}
          className={`tab${activeTab === "commissions" ? " tab--active" : ""}`}
        >
          Commission Records
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("reports")}
          className={`tab${activeTab === "reports" ? " tab--active" : ""}`}
        >
          Reports & Analytics
        </button>
      </div>

      {/* TAB 1: COMMISSIONS */}
      {activeTab === "commissions" && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card__icon">💼</div>
              <div>
                <p className="stat-card__label">Total Commissions</p>
                <p className="stat-card__value">{commissions.length}</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__icon">💵</div>
              <div>
                <p className="stat-card__label">Total Amount</p>
                <p className="stat-card__value">₹{totalCommission.toLocaleString("en-IN")}</p>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__icon">📊</div>
              <div>
                <p className="stat-card__label">Average Commission</p>
                <p className="stat-card__value">₹{Math.round(avgCommission).toLocaleString("en-IN")}</p>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="filter-row">
              <SearchBar
                placeholder="Search by name, email, or employee ID…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <select
                className="input"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Commission status"
              >
                <option value="all">All statuses</option>
                <option value="calculated">Calculated</option>
                <option value="approved">Approved</option>
              </select>
              <input
                type="date"
                className="input"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                aria-label="Period start"
              />
              <input
                type="date"
                className="input"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                aria-label="Period end"
              />
              <button
                type="button"
                className="btn-primary"
                onClick={fetchCommissions}
                disabled={loading}
              >
                {loading ? "Loading…" : "Refresh"}
              </button>
            </div>
            {canManagePayroll && (
              <div className="filter-row" style={{ marginTop: "0.75rem" }}>
                {isAdmin && (
                  <>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleApproveCalculated}
                      disabled={actionLoading}
                    >
                      Approve calculated (period)
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
            {actionMessage && (
              <p className="banner" style={{ marginTop: "0.75rem" }}>
                {actionMessage}
              </p>
            )}
          </div>

          {!isAdmin && (
            <div className="banner">
              <strong>Personal view:</strong> You&apos;re viewing your commissions only. Contact an admin for team-wide data.
            </div>
          )}

          <div className="panel">
            <div className="panel__header">
              <h2 className="panel__title">Commission Records</h2>
              <span className="pill">{filteredCommissions.length} records</span>
            </div>

            {loading ? (
              <div style={styles.loadingState}>
                <p>⏳ Loading commissions...</p>
              </div>
            ) : filteredCommissions.length === 0 ? (
              <div style={styles.emptyState}>
                <div style={styles.emptyIcon}>📊</div>
                <p style={styles.emptyText}>
                  {searchTerm ? "No matching commissions found" : "No commissions available yet"}
                </p>
                <p style={styles.emptyHint}>
                  {isAdmin
                    ? "📈 Tip: Upload orders to generate commissions for employees"
                    : "💡 Tip: Commissions will appear here once your manager uploads orders"}
                </p>
              </div>
            ) : (
              <div style={styles.tableWrapper}>
                <table style={styles.table}>
                  <thead>
                    <tr style={styles.tableHeadRow}>
                      <th style={styles.tableHeaderCell}>Employee</th>
                      <th style={styles.tableHeaderCell}>Email</th>
                      <th style={styles.tableHeaderCell}>Employee ID</th>
                      <th style={styles.tableHeaderCell}>Order ID</th>
                      <th style={styles.tableHeaderCell} align="right">
                        Commission Amount
                      </th>
                      <th style={styles.tableHeaderCell}>Status</th>
                      <th style={styles.tableHeaderCell}>Order Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCommissions.map((commission, index) => (
                      <tr key={commission.id} style={styles.tableRow}>
                        <td style={styles.tableCell}>
                          <span style={styles.nameCell}>
                            {index + 1}. {commission.employee_name || "Unknown"}
                          </span>
                        </td>
                        <td style={styles.tableCell}>{commission.employee_email || "N/A"}</td>
                        <td style={styles.tableCell}>
                          <span className="employee-badge">{commission.employee_id || "N/A"}</span>
                        </td>
                        <td style={styles.tableCell}>
                          {commission.order_id || "—"}
                        </td>
                        <td style={{ ...styles.tableCell, textAlign: "right" }}>
                          <span className="amount-positive" style={styles.amountCell}>
                            ₹
                            {parseFloat(commission.commission_amount).toLocaleString("en-IN", {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </span>
                        </td>
                        <td style={styles.tableCell}>
                          <span
                            className={`pill ${
                              commission.status === "approved"
                                ? "pill--success"
                                : ""
                            }`}
                          >
                            {commission.status === "approved"
                              ? "Approved"
                              : "Calculated"}
                          </span>
                        </td>
                        <td style={styles.tableCell}>
                          {commission.order_date
                            ? new Date(commission.order_date).toLocaleDateString("en-IN")
                            : "N/A"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* TAB 2: REPORTS */}
      {activeTab === "reports" && (
        <>
          {/* Filters */}
          <div style={styles.filterCard}>
            <div style={styles.filterGrid}>
              <div style={styles.filterSection}>
                <label style={styles.label}>Report Type:</label>
                <select
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value)}
                  style={styles.select}
                >
                  <option value="commission-summary">Commission Summary</option>
                  <option value="sales-performance">Sales Performance</option>
                  <option value="employee-earnings">Employee Earnings</option>
                  <option value="period-analytics">Period Analytics</option>
                </select>
              </div>

              {reportType === "period-analytics" && (
                <div style={styles.filterSection}>
                  <label style={styles.label}>Period:</label>
                  <select
                    value={period}
                    onChange={(e) => setPeriod(e.target.value)}
                    style={styles.select}
                  >
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="annual">Annual</option>
                  </select>
                </div>
              )}

              <div style={styles.filterSection}>
                <label style={styles.label}>Start Date:</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  style={styles.input}
                />
              </div>

              <div style={styles.filterSection}>
                <label style={styles.label}>End Date:</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  style={styles.input}
                />
              </div>
            </div>

            <div style={styles.buttonGroup}>
              <button
                onClick={handleApplyFilter}
                style={styles.buttonPrimary}
                disabled={reportLoading}
              >
                {reportLoading ? "⏳ Loading..." : "🔍 Apply Filter"}
              </button>
              {reportData && (
                <button onClick={exportToCSV} style={styles.buttonSecondary}>
                  📥 Export CSV
                </button>
              )}
            </div>
          </div>

          {/* Error Message */}
          {reportError && (
            <div style={styles.errorCard}>
              <p>{reportError}</p>
            </div>
          )}

          {/* Report Content */}
          {reportLoading ? (
            <div style={styles.loadingCard}>
              <p>⏳ Loading report...</p>
            </div>
          ) : reportData ? (
            <>
              {/* Summary Cards */}
              {reportType === "commission-summary" && (
                <div style={styles.metricsGrid}>
                  <div style={styles.metricCard}>
                    <p style={styles.metricLabel}>💰 Total Commission</p>
                    <p style={styles.metricValue}>
                      ₹{(reportData.total_commission || 0).toLocaleString("en-IN")}
                    </p>
                  </div>
                  <div style={styles.metricCard}>
                    <p style={styles.metricLabel}>📈 Commission Count</p>
                    <p style={styles.metricValue}>{reportData.total_count || 0}</p>
                  </div>
                  <div style={styles.metricCard}>
                    <p style={styles.metricLabel}>📊 Average Commission</p>
                    <p style={styles.metricValue}>
                      ₹{Math.round(reportData.avg_commission || 0).toLocaleString("en-IN")}
                    </p>
                  </div>
                </div>
              )}

              {/* Report Table */}
              <div style={styles.tableCard}>
                <h3 style={styles.tableTitle}>{reportType.toUpperCase().replace("-", " ")} Report</h3>
                <div style={styles.tableWrapper}>
                  <table style={styles.table}>
                    <thead>
                      <tr style={styles.tableHeadRow}>
                        {reportType === "commission-summary" && (
                          <>
                            <th style={styles.tableHeaderCell}>Employee Name</th>
                            <th style={styles.tableHeaderCell}>Email</th>
                            <th style={styles.tableHeaderCell} align="right">Total Commission</th>
                            <th style={styles.tableHeaderCell} align="right">Count</th>
                          </>
                        )}
                        {reportType === "sales-performance" && (
                          <>
                            <th style={styles.tableHeaderCell}>Employee ID</th>
                            <th style={styles.tableHeaderCell}>Position</th>
                            <th style={styles.tableHeaderCell} align="right">Total Sales</th>
                            <th style={styles.tableHeaderCell} align="right">Order Count</th>
                          </>
                        )}
                        {reportType === "employee-earnings" && (
                          <>
                            <th style={styles.tableHeaderCell}>Employee Name</th>
                            <th style={styles.tableHeaderCell}>Email</th>
                            <th style={styles.tableHeaderCell} align="right">Total Earnings</th>
                            <th style={styles.tableHeaderCell} align="right">Commission Count</th>
                          </>
                        )}
                        {reportType === "period-analytics" && (
                          <>
                            <th style={styles.tableHeaderCell}>Period</th>
                            <th style={styles.tableHeaderCell} align="right">Total</th>
                            <th style={styles.tableHeaderCell} align="right">Count</th>
                          </>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {reportType === "commission-summary" && reportData.top_earners?.map((item, idx) => (
                        <tr key={idx} style={styles.tableRow}>
                          <td style={styles.tableCell}>{item.employee__name || item.employee_id}</td>
                          <td style={styles.tableCell}>{item.employee__email || "N/A"}</td>
                          <td style={{ ...styles.tableCell, textAlign: "right" }}>₹{item.total?.toLocaleString("en-IN")}</td>
                          <td style={{ ...styles.tableCell, textAlign: "right" }}>{item.count}</td>
                        </tr>
                      ))}
                      {reportType === "sales-performance" && reportData.sales_data?.map((item, idx) => (
                        <tr key={idx} style={styles.tableRow}>
                          <td style={styles.tableCell}>{item.employee_id}</td>
                          <td style={styles.tableCell}>{item.position_name || "N/A"}</td>
                          <td style={{ ...styles.tableCell, textAlign: "right" }}>₹{item.total_sales?.toLocaleString("en-IN")}</td>
                          <td style={{ ...styles.tableCell, textAlign: "right" }}>{item.order_count}</td>
                        </tr>
                      ))}
                      {reportType === "employee-earnings" && reportData.earnings?.map((item, idx) => (
                        <tr key={idx} style={styles.tableRow}>
                          <td style={styles.tableCell}>{item.employee__name || "N/A"}</td>
                          <td style={styles.tableCell}>{item.employee__email || "N/A"}</td>
                          <td style={{ ...styles.tableCell, textAlign: "right" }}>₹{item.total_earnings?.toLocaleString("en-IN")}</td>
                          <td style={{ ...styles.tableCell, textAlign: "right" }}>{item.commission_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div style={styles.emptyState}>
              <div style={styles.emptyIcon}>📊</div>
              <p style={styles.emptyText}>No report data available</p>
              <p style={styles.emptyHint}>Click "Apply Filter" to generate a report</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

const styles = {
  container: { padding: "0px" },
  header: { marginBottom: "20px" },
  title: {
    fontSize: "32px",
    fontWeight: "700",
    color: "var(--text-primary)",
    margin: "0 0 10px 0",
  },
  subtitle: { fontSize: "16px", color: "var(--text-secondary)", margin: "0" },
  tabContainer: {
    display: "flex",
    gap: "10px",
    marginBottom: "30px",
    borderBottom: "2px solid var(--border-color)",
    padding: "0 0 10px 0",
  },
  tab: {
    padding: "12px 24px",
    border: "none",
    backgroundColor: "transparent",
    cursor: "pointer",
    fontSize: "15px",
    fontWeight: "600",
    transition: "all 0.3s ease",
    borderBottom: "3px solid transparent",
    color: "var(--text-secondary)",
  },
  tabActive: {
    color: "var(--primary-light)",
    borderBottomColor: "var(--primary-light)",
    backgroundColor: "rgba(99, 102, 241, 0.12)",
  },
  tabInactive: { color: "var(--text-secondary)" },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "20px",
    marginBottom: "30px",
  },
  statCard: {
    background: "var(--bg-card)",
    padding: "24px",
    borderRadius: "12px",
    display: "flex",
    gap: "16px",
    alignItems: "center",
    boxShadow: "var(--shadow-md)",
    border: "1px solid var(--border-color)",
  },
  statIcon: { fontSize: "32px" },
  statLabel: {
    fontSize: "12px",
    color: "var(--text-muted)",
    fontWeight: "600",
    margin: "0 0 4px 0",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  statValue: {
    fontSize: "24px",
    fontWeight: "700",
    color: "var(--text-primary)",
    margin: "0",
  },
  filterCard: {
    background: "var(--bg-card)",
    padding: "20px",
    borderRadius: "12px",
    marginBottom: "30px",
    boxShadow: "var(--shadow-md)",
    border: "1px solid var(--border-color)",
  },
  filterGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "15px",
    marginBottom: "15px",
  },
  filterSection: { display: "flex", flexDirection: "column" },
  label: {
    fontSize: "12px",
    fontWeight: "600",
    color: "var(--text-muted)",
    marginBottom: "6px",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  select: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid var(--border-color)",
    fontSize: "14px",
    backgroundColor: "var(--bg-darker)",
    color: "var(--text-primary)",
    cursor: "pointer",
  },
  input: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid var(--border-color)",
    fontSize: "14px",
    backgroundColor: "var(--bg-darker)",
    color: "var(--text-primary)",
  },
  filterRow: { display: "flex", gap: "12px", alignItems: "flex-end" },
  buttonGroup: { display: "flex", gap: "10px", justifyContent: "flex-start" },
  buttonPrimary: {
    padding: "10px 16px",
    borderRadius: "8px",
    background: "linear-gradient(135deg, var(--primary-color), var(--secondary-color))",
    color: "white",
    border: "none",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "14px",
  },
  buttonSecondary: {
    padding: "10px 16px",
    borderRadius: "8px",
    background: "var(--success-color)",
    color: "white",
    border: "none",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "14px",
  },
  refreshBtn: {
    padding: "10px 16px",
    background: "linear-gradient(135deg, var(--primary-color), var(--secondary-color))",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "14px",
    whiteSpace: "nowrap",
  },
  metricsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "20px",
    marginBottom: "30px",
  },
  metricCard: {
    background: "var(--bg-card)",
    padding: "24px",
    borderRadius: "12px",
    boxShadow: "var(--shadow-md)",
    border: "1px solid var(--border-color)",
  },
  metricLabel: {
    fontSize: "14px",
    color: "var(--text-muted)",
    marginBottom: "8px",
    fontWeight: "600",
  },
  metricValue: {
    fontSize: "28px",
    fontWeight: "700",
    color: "var(--text-primary)",
  },
  tableCard: {
    background: "var(--bg-card)",
    borderRadius: "12px",
    padding: "24px",
    marginBottom: "30px",
    boxShadow: "var(--shadow-md)",
    overflowX: "auto",
    border: "1px solid var(--border-color)",
  },
  infoBanner: {
    background: "rgba(59, 130, 246, 0.12)",
    border: "1px solid rgba(59, 130, 246, 0.4)",
    borderRadius: "10px",
    padding: "12px 16px",
    marginBottom: "20px",
    color: "var(--text-secondary)",
  },
  tableHeader: {
    paddingBottom: "16px",
    borderBottom: "2px solid var(--border-color)",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
  },
  tableTitle: {
    fontSize: "18px",
    fontWeight: "700",
    color: "var(--text-primary)",
    margin: "0",
  },
  recordCount: {
    fontSize: "12px",
    color: "var(--text-secondary)",
    fontWeight: "600",
    background: "var(--bg-light)",
    padding: "4px 12px",
    borderRadius: "20px",
  },
  tableWrapper: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse" },
  tableHeadRow: {
    background: "var(--bg-darker)",
    borderBottom: "2px solid var(--border-color)",
  },
  tableHeaderCell: {
    padding: "16px",
    textAlign: "left",
    fontSize: "12px",
    fontWeight: "700",
    color: "var(--text-muted)",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  tableRow: {
    borderBottom: "1px solid var(--border-light)",
    transition: "background 0.2s ease",
  },
  tableCell: {
    padding: "16px",
    fontSize: "14px",
    color: "var(--text-secondary)",
  },
  nameCell: { fontWeight: "600", color: "var(--text-primary)" },
  badge: {},
  amountCell: { fontSize: "16px", fontWeight: "700", color: "var(--success-color)" },
  loadingState: {
    padding: "60px",
    textAlign: "center",
    color: "var(--text-secondary)",
    fontSize: "16px",
  },
  loadingCard: {
    background: "var(--bg-card)",
    padding: "60px",
    borderRadius: "12px",
    textAlign: "center",
    fontSize: "18px",
    color: "var(--text-secondary)",
    boxShadow: "var(--shadow-md)",
    border: "1px solid var(--border-color)",
  },
  errorCard: {
    background: "rgba(220, 38, 38, 0.12)",
    padding: "16px",
    borderRadius: "8px",
    marginBottom: "20px",
    border: "1px solid var(--danger-color)",
    color: "var(--danger-color)",
  },
  emptyState: {
    padding: "60px",
    textAlign: "center",
    background: "var(--bg-card)",
    borderRadius: "12px",
    border: "1px solid var(--border-color)",
    boxShadow: "var(--shadow-md)",
  },
  emptyIcon: { fontSize: "48px", marginBottom: "16px" },
  emptyText: {
    fontSize: "18px",
    color: "var(--text-primary)",
    fontWeight: "600",
    margin: "0 0 8px 0",
  },
  emptyHint: { fontSize: "14px", color: "var(--text-muted)", margin: "0" },
};

export default Commissions;
