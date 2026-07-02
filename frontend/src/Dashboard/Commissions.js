import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../api";
import SearchBar from "../Components/SearchBar";
import PageHeader from "../Components/PageHeader";
import StatusPill from "../Components/StatusPill";
import DatePickerField from "../Components/DatePickerField";
import { formatMoney } from "../utils/currency";
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

function Commissions() {
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [canManagePayroll, setCanManagePayroll] = useState(false);

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
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

  const fetchCommissions = useCallback(async (overrides = {}) => {
    setLoading(true);
    setLoadError("");
    try {
      const params = new URLSearchParams();
      const status = overrides.status ?? statusFilter;
      const start = overrides.startDate ?? startDate;
      const end = overrides.endDate ?? endDate;
      if (status !== "all") params.append("status", status);
      if (start) params.append("start_date", start);
      if (end) params.append("end_date", end);
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

  useEffect(() => {
    fetchUserProfile();
  }, [fetchUserProfile]);

  useEffect(() => {
    fetchCommissions();
  }, [fetchCommissions]);

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
      const approved = response.data.approved ?? 0;
      if (approved === 0) {
        setActionMessage(
          "No calculated commissions found for this period. Check dates and status filter."
        );
      } else {
        setStatusFilter("approved");
        setActionMessage(`Approved ${approved} commission(s). Status updated to Approved.`);
        await fetchCommissions({ status: "approved" });
        return;
      }
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

  return (
    <div className="commissions-page">
      <PageHeader
        badge="Payroll"
        title="Commissions"
        subtitle={
          isAdmin
            ? "Review commission records, approve calculated payouts, and export payroll."
            : "View your commission records and status."
        }
      />

      <div className="panel commissions-toolbar">
        <div className="commissions-toolbar__block">
          <h3 className="commissions-toolbar__heading">Filters</h3>
          <div className="commissions-toolbar__grid commissions-toolbar__grid--filters">
            <div className="commissions-toolbar__field commissions-toolbar__field--search">
              <label className="commissions-toolbar__field-label">Search</label>
              <SearchBar
                className="commissions-filter-search"
                placeholder="Rep, order, plan…"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <div className="commissions-toolbar__field">
              <label className="commissions-toolbar__field-label" htmlFor="commissions-status">
                Status
              </label>
              <select
                id="commissions-status"
                className="input commissions-filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">All statuses</option>
                <option value="calculated">Calculated</option>
                <option value="manager_approved">Manager approved</option>
                <option value="approved">Finance approved</option>
                <option value="paid">Paid</option>
              </select>
            </div>

            <div className="commissions-toolbar__field">
              <DatePickerField
                id="commissions-start-date"
                label="From"
                value={startDate}
                onChange={setStartDate}
                maxDate={endDate || undefined}
                fullWidth
                size="small"
                className="commissions-filter-date"
              />
            </div>

            <div className="commissions-toolbar__field">
              <DatePickerField
                id="commissions-end-date"
                label="To"
                value={endDate}
                onChange={setEndDate}
                minDate={startDate || undefined}
                fullWidth
                size="small"
                className="commissions-filter-date"
              />
            </div>

            <div className="commissions-toolbar__field commissions-toolbar__field--button">
              <span className="commissions-toolbar__field-label commissions-toolbar__field-label--spacer">
                &nbsp;
              </span>
              <button type="button" className="btn-primary commissions-toolbar__btn" onClick={fetchCommissions} disabled={loading}>
                {loading ? "Loading…" : "Refresh"}
              </button>
            </div>
          </div>
        </div>

        {canManagePayroll && (
          <div className="commissions-toolbar__block commissions-toolbar__block--actions">
            <h3 className="commissions-toolbar__heading">Actions</h3>
            <div className="commissions-toolbar__grid commissions-toolbar__grid--actions">
              {isAdmin && (
                <>
                  <button
                    type="button"
                    className="btn-secondary commissions-toolbar__btn"
                    onClick={handleApproveCalculated}
                    disabled={actionLoading}
                  >
                    Approve calculated
                  </button>
                  <button
                    type="button"
                    className="btn-secondary commissions-toolbar__btn"
                    onClick={handleRecalculate}
                    disabled={actionLoading}
                  >
                    Recalculate period
                  </button>
                </>
              )}
              <button
                type="button"
                className="btn-secondary commissions-toolbar__btn"
                onClick={handlePayrollExport}
                disabled={actionLoading}
              >
                Export payroll CSV
              </button>
            </div>
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
          <h2 className="commissions-records__title">Commission records</h2>
          <span className="commissions-records__count">
            {filteredCommissions.length} shown
          </span>
        </div>

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
    </div>
  );
}

export default Commissions;
