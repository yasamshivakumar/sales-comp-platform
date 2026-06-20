import { useState, useEffect, useRef, useCallback } from "react";
import { Navigate } from "react-router-dom";
import api from "../api";
import SearchBar from "../Components/SearchBar";
import PageHeader from "../Components/PageHeader";
import DatePickerField from "../Components/DatePickerField";
import DisputesPanel from "../Enterprise/DisputesPanel";
import CommissionExplanationModal from "../Components/CommissionExplanationModal";
import StatusPill from "../Components/StatusPill";
import { formatMoney } from "../utils/currency";
import "../Components/enterprise.css";
import "./commissions.css";

function formatCompactDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function Commissions() {
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [isManager, setIsManager] = useState(false);
  const [isFinance, setIsFinance] = useState(false);
  const [canManagePayroll, setCanManagePayroll] = useState(false);
  const [profileLoaded, setProfileLoaded] = useState(false);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [actionMessage, setActionMessage] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [listLimited, setListLimited] = useState(false);
  const [totalCount, setTotalCount] = useState(null);
  const [disputePrefill, setDisputePrefill] = useState(null);
  const disputesPanelRef = useRef(null);
  const [explainId, setExplainId] = useState(null);

  const clearDisputePrefill = useCallback(() => setDisputePrefill(null), []);

  const openDisputeFor = (commission) => {
    setDisputePrefill(commission);
    window.setTimeout(() => {
      disputesPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  };

  useEffect(() => {
    fetchUserProfile();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!profileLoaded || !canManagePayroll) return;
    const timer = window.setTimeout(
      () => fetchCommissions(searchTerm),
      searchTerm.trim() ? 300 : 0
    );
    return () => window.clearTimeout(timer);
  }, [searchTerm, statusFilter, profileLoaded, canManagePayroll]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchUserProfile = async () => {
    try {
      const response = await api.get("user-profile/");
      const admin = Boolean(response.data.is_admin);
      const finance = Boolean(response.data.is_finance);
      const manager = Boolean(response.data.is_manager);
      setIsAdmin(admin);
      setIsFinance(finance);
      setIsManager(manager);
      setCanManagePayroll(admin || finance || manager);
    } catch {
      setIsAdmin(false);
      setIsManager(false);
      setCanManagePayroll(false);
    } finally {
      setProfileLoaded(true);
    }
  };

  const fetchCommissions = async (search = searchTerm) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      const validStatuses = ["calculated", "manager_approved", "approved", "paid"];
      if (validStatuses.includes(statusFilter)) {
        params.append("status", statusFilter);
      }
      const term = (search || "").trim();
      if (term) {
        params.append("q", term);
      } else {
        params.append("limit", "50");
      }
      const qs = params.toString();
      const response = await api.get(qs ? `commissions/?${qs}` : "commissions/");
      const data = response.data;
      if (Array.isArray(data)) {
        setCommissions(data);
        setListLimited(false);
        setTotalCount(data.length);
      } else {
        setCommissions(data.results || []);
        setListLimited(Boolean(data.limited));
        setTotalCount(data.count ?? null);
      }
    } catch (err) {
      console.error("Failed to load commissions", err);
    } finally {
      setLoading(false);
    }
  };

  const runApproval = async (endpoint, label) => {
    if (!startDate || !endDate) {
      setActionMessage("Set start and end dates for period-based approval.");
      return;
    }
    setActionLoading(true);
    setActionMessage("");
    try {
      const response = await api.post(endpoint, {
        start_date: startDate,
        end_date: endDate,
      });
      setActionMessage(`${label}: ${response.data.approved} commission(s).`);
      fetchCommissions();
    } catch (err) {
      setActionMessage(err.response?.data?.error || `${label} failed.`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleManagerApprove = () =>
    runApproval("commissions/approve/manager/", "Manager approval");

  const handleFinanceApprove = () =>
    runApproval("commissions/approve/finance/", "Finance approval");

  const handleAdminApprove = () =>
    runApproval("commissions/approve/", "Admin approval");

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
    const employeeFilter = searchTerm.trim();
    const scopeText = employeeFilter
      ? `employees matching "${employeeFilter}"`
      : "all employees";
    const proceed = window.confirm(
      `Recalculate orders for ${scopeText} between ${startDate} and ${endDate}?`
    );
    if (!proceed) {
      return;
    }
    const force = window.confirm(
      "Also replace locked commissions that are manager-approved, finance-approved, or paid?\n\nOK = replace locked commissions too.\nCancel = skip locked commissions."
    );
    setActionLoading(true);
    setActionMessage("");
    try {
      const payload = {
        start_date: startDate,
        end_date: endDate,
        force,
      };
      if (employeeFilter) {
        payload.q = employeeFilter;
      }
      const response = await api.post("commissions/recalculate/", payload);
      const s = response.data;
      const scopeNote = s.scoped
        ? ` (filtered: "${s.employee_q}")`
        : " (all employees)";
      const skippedApproved = Number(s.skipped_approved || 0);
      const failed = Number(s.failed || 0);
      const resultParts = [`Recalculated ${s.processed} order(s)${scopeNote}.`];
      if (skippedApproved > 0) {
        resultParts.push(`Skipped ${skippedApproved} locked/approved order(s).`);
      }
      if (failed > 0) {
        resultParts.push(`Failed: ${failed}.`);
      }
      if (skippedApproved === 0 && failed === 0) {
        resultParts.push("No locked/approved orders were skipped.");
      }
      setActionMessage(resultParts.join(" "));
      fetchCommissions(searchTerm);
    } catch (err) {
      setActionMessage(err.response?.data?.error || "Recalculate failed.");
    } finally {
      setActionLoading(false);
    }
  };

  if (profileLoaded && !canManagePayroll) {
    return <Navigate to="/statement" replace />;
  }

  return (
    <div className="commissions-page">
      <PageHeader badge="Payroll" title="Commission management" />

      {canManagePayroll && (
        <>
          <div className="panel commissions-toolbar">
            <div className="commissions-toolbar__section">
              <SearchBar
                className="commissions-filter-search"
                placeholder="Search employee or order ID…"
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
                <option value="approved">Approved</option>
                <option value="paid">Paid</option>
              </select>
              <DatePickerField
                label="Period start"
                value={startDate}
                onChange={setStartDate}
                maxDate={endDate || undefined}
                fullWidth={false}
                className="commissions-filter-date"
                slotProps={{ textField: { className: "commissions-filter-date" } }}
              />
              <DatePickerField
                label="Period end"
                value={endDate}
                onChange={setEndDate}
                minDate={startDate || undefined}
                fullWidth={false}
                className="commissions-filter-date"
                slotProps={{ textField: { className: "commissions-filter-date" } }}
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

            <div className="commissions-toolbar__section">
              <span className="commissions-toolbar__label">Actions</span>
              {(isManager || isAdmin) && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleManagerApprove}
                  disabled={actionLoading}
                >
                  Manager approve
                </button>
              )}
              {(isFinance || isAdmin) && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleFinanceApprove}
                  disabled={actionLoading}
                >
                  Finance approve
                </button>
              )}
              {isAdmin && (
                <>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleAdminApprove}
                    disabled={actionLoading}
                    title="Skip manager step"
                  >
                    Admin approve
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleRecalculate}
                    disabled={actionLoading}
                    title={
                      searchTerm.trim()
                        ? `Recalculate only employees matching "${searchTerm.trim()}"`
                        : "Recalculate all employees in the date range"
                    }
                  >
                    Recalculate
                    {searchTerm.trim() ? " (filtered)" : ""}
                  </button>
                </>
              )}
              <button
                type="button"
                className="btn-secondary"
                onClick={handlePayrollExport}
                disabled={actionLoading}
              >
                Export CSV
              </button>
            </div>

            {actionMessage && (
              <p className="banner commissions-banner">{actionMessage}</p>
            )}
          </div>

          {!isAdmin && (
            <div className="banner commissions-banner commissions-banner--info">
              <strong>Personal view:</strong> You&apos;re viewing your commissions only. Contact an
              admin for team-wide data.
            </div>
          )}

          <div className="panel commissions-records">
            <div className="commissions-records__header">
              <h2 className="commissions-records__title">Commission records</h2>
              <span className="commissions-records__count">
                {commissions.length} rows
                {totalCount != null && listLimited && !searchTerm.trim()
                  ? ` of ${totalCount}`
                  : ""}
              </span>
            </div>
            {searchTerm.trim() && (
              <p className="commissions-records__hint">
                Recalculate applies only to employees matching &quot;{searchTerm.trim()}&quot;.
                Clear search to recalculate everyone in the date range.
              </p>
            )}
            {listLimited && !searchTerm.trim() && (
              <p className="commissions-records__hint">
                Showing the 50 most recently calculated of {totalCount ?? "many"} records.
                Search by employee name or order ID to find others.
              </p>
            )}

            <div className="commissions-table-wrap">
              <table className="commissions-table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Email</th>
                    <th>Emp ID</th>
                    <th>Order</th>
                    <th className="commissions-table__num">Amount</th>
                    <th>Status</th>
                    <th>Order date</th>
                    {canManagePayroll && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={canManagePayroll ? 8 : 7} className="commissions-table__state">
                        Loading commissions…
                      </td>
                    </tr>
                  ) : commissions.length === 0 ? (
                    <tr>
                      <td colSpan={canManagePayroll ? 8 : 7} className="commissions-table__state">
                        <div className="commissions-table__state-icon" aria-hidden="true">
                          📊
                        </div>
                        <p className="commissions-table__state-title">
                          {searchTerm ? "No matching records" : "No commission records"}
                        </p>
                        <p className="commissions-table__state-hint">
                          {isAdmin
                            ? "Upload orders to generate commissions."
                            : "Records appear after orders are processed."}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    commissions.map((commission) => (
                      <tr key={commission.id}>
                        <td>
                          <span className="commissions-table__employee">
                            {commission.employee_name || "—"}
                          </span>
                        </td>
                        <td>
                          <span className="commissions-table__email" title={commission.employee_email || ""}>
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
                        <td className="commissions-table__num">
                          <button
                            type="button"
                            className="amount-positive commissions-table__amount commissions-table__amount-btn"
                            onClick={() => setExplainId(commission.id)}
                            title="View commission explanation"
                          >
                            {formatMoney(commission.commission_amount, commission.currency)}
                          </button>
                        </td>
                        <td>
                          <div className="commissions-table__status">
                            <StatusPill status={commission.status} compact />
                            {commission.has_open_dispute && (
                              <StatusPill status="open" label="Dispute" compact />
                            )}
                          </div>
                        </td>
                        <td>
                          <span className="commissions-table__date">
                            {formatCompactDate(commission.order_date)}
                          </span>
                        </td>
                        {canManagePayroll && (
                          <td className="commissions-table__actions">
                            {commission.has_open_dispute ? (
                              <span className="commissions-table__dispute-open">Dispute open</span>
                            ) : (
                              <button
                                type="button"
                                className="btn-secondary commissions-table__dispute-btn"
                                onClick={() => openDisputeFor(commission)}
                              >
                                Dispute
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <DisputesPanel
            panelRef={disputesPanelRef}
            canResolve={isAdmin || isManager || isFinance}
            prefillCommission={disputePrefill}
            onPrefillConsumed={clearDisputePrefill}
          />

          <CommissionExplanationModal
            open={Boolean(explainId)}
            commissionId={explainId}
            onClose={() => setExplainId(null)}
            periodStart={startDate}
            periodEnd={endDate}
          />
        </>
      )}
    </div>
  );
}

export default Commissions;
