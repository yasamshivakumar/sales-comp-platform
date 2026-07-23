import { useCallback, useEffect, useMemo, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import DatePickerField from "../Components/DatePickerField";
import { formatMoney } from "../utils/currency";
import CommissionGrid from "./CommissionGrid";
import { CommissionProcessStatus, CommissionSummary } from "./CommissionSummary";
import CommissionWorkspace from "./CommissionWorkspace";
import "./commissionCenter.css";

function buildQs(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value != null && String(value).trim() !== "" && value !== "all") {
      params.set(key, value);
    }
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}

export default function CommissionCenter() {
  const [profile, setProfile] = useState(null);
  const [filters, setFilters] = useState({
    start_date: "",
    end_date: "",
    status: "all",
    employee: "",
    employee_id: "",
    plan: "",
    role: "",
    department: "",
    territory: "",
    approval_status: "all",
    min_commission: "",
    max_commission: "",
    calculation_scope: "all",
  });
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState(() => new Set());
  const [actionBusy, setActionBusy] = useState(false);
  const [workspaceRow, setWorkspaceRow] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [adjustBusy, setAdjustBusy] = useState(false);
  const [exportMenu, setExportMenu] = useState(false);

  const isAdmin = Boolean(profile?.is_admin);
  const isFinance = Boolean(profile?.is_finance);
  const isManager = Boolean(profile?.is_manager);
  const canManage = isAdmin || isFinance || isManager;
  const canEditAdjustments = isAdmin || isFinance;
  const currency = "INR";

  useEffect(() => {
    api
      .get("user-profile/")
      .then((res) => setProfile(res.data))
      .catch(() => setProfile(null));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = buildQs(filters);
      const [sumRes, gridRes] = await Promise.all([
        api.get(`commissions/operations-summary/${qs}`),
        api.get(`commissions/operations-grid/${qs}`),
      ]);
      setSummary(sumRes.data);
      setRows(gridRes.data?.results || []);
      setSelected(new Set());
    } catch (err) {
      setSummary(null);
      setRows([]);
      setError(getApiErrorMessage(err) || "Failed to load commission operations.");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  const setFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const openWorkspace = async (row) => {
    setWorkspaceRow(row);
    setDetail(null);
    setDetailLoading(true);
    try {
      const params = new URLSearchParams();
      if (row.commission_ids?.length) {
        params.set("commission_ids", row.commission_ids.join(","));
      }
      if (row.employee_email) params.set("employee_email", row.employee_email);
      if (row.period_start) params.set("period_start", row.period_start);
      if (row.period_end) params.set("period_end", row.period_end);
      const res = await api.get(`commissions/operations-detail/?${params}`);
      setDetail(res.data);
    } catch (err) {
      setDetail(null);
      setMessage(getApiErrorMessage(err) || "Failed to open statement workspace.");
    } finally {
      setDetailLoading(false);
    }
  };

  const toggleIds = (ids) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const allOn = ids.every((id) => next.has(id));
      ids.forEach((id) => {
        if (allOn) next.delete(id);
        else next.add(id);
      });
      return next;
    });
  };

  const toggleAll = (ids) => {
    setSelected((prev) => {
      const allOn = ids.length > 0 && ids.every((id) => prev.has(id));
      if (allOn) return new Set();
      return new Set(ids);
    });
  };

  const runBulk = async (action, extra = {}) => {
    const ids = Array.from(selected);
    if (!ids.length) {
      setMessage("Select at least one commission row (checkbox).");
      return;
    }
    let comment = extra.comment;
    if (action === "reject" && !comment) {
      comment = window.prompt("Rejection reason (required):") || "";
      if (!comment.trim()) {
        setMessage("Rejection cancelled — reason required.");
        return;
      }
    }
    if (action === "assign_reviewer" && !extra.reviewer_email) {
      const email = window.prompt("Reviewer email:") || "";
      if (!email.trim()) {
        setMessage("Assign reviewer cancelled.");
        return;
      }
      extra = { ...extra, reviewer_email: email.trim() };
    }
    setActionBusy(true);
    setMessage("");
    try {
      const res = await api.post("commissions/operations-bulk/", {
        action,
        commission_ids: ids,
        comment,
        ...extra,
      });
      setMessage(
        `Bulk ${action}: updated ${res.data.updated ?? res.data.processed ?? 0}.`
      );
      await load();
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Bulk action failed.");
    } finally {
      setActionBusy(false);
    }
  };

  const handlePeriodRecalculate = async () => {
    if (!filters.start_date || !filters.end_date) {
      setMessage("Set From and To dates to recalculate a period.");
      return;
    }
    const force = window.confirm(
      "Recalculate all orders in this period?\n\nOK = replace approved commissions too.\nCancel = skip locked commissions."
    );
    setActionBusy(true);
    try {
      const res = await api.post("commissions/recalculate/", {
        start_date: filters.start_date,
        end_date: filters.end_date,
        force,
      });
      const s = res.data;
      setMessage(
        `Recalculated ${s.processed} order(s). Skipped: ${s.skipped_approved}. Failed: ${s.failed}.`
      );
      await load();
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Recalculate failed.");
    } finally {
      setActionBusy(false);
    }
  };

  const handleExport = async (report, format = "csv") => {
    setExportMenu(false);
    setActionBusy(true);
    setMessage("");
    try {
      const qs = buildQs({ ...filters, report, format });
      const res = await api.get(`commissions/operations-export/${qs}`, {
        responseType: "blob",
      });
      const ext = format === "pdf" ? "html" : "csv";
      downloadBlob(res.data, `${report}-commissions.${ext}`);
      setMessage(`${report} export downloaded.`);
    } catch {
      setMessage("Export failed.");
    } finally {
      setActionBusy(false);
    }
  };

  const createAdjustment = async (payload) => {
    setAdjustBusy(true);
    try {
      await api.post("commissions/adjustments/", payload);
      setMessage("Adjustment posted.");
      if (workspaceRow) await openWorkspace(workspaceRow);
      await load();
    } catch (err) {
      setMessage(getApiErrorMessage(err) || "Failed to post adjustment.");
    } finally {
      setAdjustBusy(false);
    }
  };

  const selectedCount = selected.size;
  const filterFields = useMemo(
    () => [
      { key: "employee", label: "Employee", type: "text" },
      { key: "employee_id", label: "Employee ID", type: "text" },
      { key: "plan", label: "Plan", type: "text" },
      { key: "role", label: "Role", type: "text" },
      { key: "department", label: "Department", type: "text" },
      { key: "territory", label: "Territory", type: "text" },
    ],
    []
  );

  return (
    <div className="co-root">
      <header className="co-header">
        <div>
          <p className="co-eyebrow">Payroll · Finance</p>
          <h1>Commission Operations Center</h1>
          <p className="co-sub">
            Review, validate, approve, adjust, and export sales commissions.
          </p>
        </div>
        <div className="co-header__actions">
          <button type="button" className="btn-secondary" onClick={load} disabled={loading}>
            Refresh
          </button>
          <div className="co-export">
            <button
              type="button"
              className="btn-primary"
              onClick={() => setExportMenu((v) => !v)}
              disabled={actionBusy}
            >
              Export
            </button>
            {exportMenu ? (
              <div className="co-export__menu">
                <button type="button" onClick={() => handleExport("payroll", "csv")}>
                  Payroll CSV
                </button>
                <button type="button" onClick={() => handleExport("finance", "csv")}>
                  Finance Report
                </button>
                <button type="button" onClick={() => handleExport("statements", "csv")}>
                  Employee Statements
                </button>
                <button type="button" onClick={() => handleExport("audit", "csv")}>
                  Commission Audit Report
                </button>
                <button type="button" onClick={() => handleExport("finance", "pdf")}>
                  Printable PDF (HTML)
                </button>
                <button type="button" onClick={() => handleExport("payroll", "xlsx")}>
                  Excel-compatible CSV
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <section className="panel co-filters">
        <h2 className="co-section-title">Filters</h2>
        <div className="co-filters__grid">
          <DatePickerField
            id="co-start"
            label="From"
            value={filters.start_date}
            onChange={(v) => setFilter("start_date", v)}
            maxDate={filters.end_date || undefined}
            fullWidth
            size="small"
          />
          <DatePickerField
            id="co-end"
            label="To"
            value={filters.end_date}
            onChange={(v) => setFilter("end_date", v)}
            minDate={filters.start_date || undefined}
            fullWidth
            size="small"
          />
          <label>
            Status
            <select
              value={filters.status}
              onChange={(e) => setFilter("status", e.target.value)}
            >
              <option value="all">All</option>
              <option value="calculated">Calculated</option>
              <option value="manager_approved">Under Review</option>
              <option value="approved">Approved</option>
              <option value="paid">Paid</option>
              <option value="rejected">Rejected</option>
              <option value="failed">Failed</option>
            </select>
          </label>
          <label>
            Approval
            <select
              value={filters.approval_status}
              onChange={(e) => setFilter("approval_status", e.target.value)}
            >
              <option value="all">All</option>
              <option value="calculated">Calculated</option>
              <option value="under_review">Under Review</option>
              <option value="approved">Finance Approved</option>
              <option value="paid">Paid</option>
              <option value="rejected">Rejected</option>
            </select>
          </label>
          {filterFields.map((f) => (
            <label key={f.key}>
              {f.label}
              <input
                type="text"
                value={filters[f.key]}
                onChange={(e) => setFilter(f.key, e.target.value)}
                placeholder={f.label}
              />
            </label>
          ))}
          <label>
            Min commission
            <input
              type="number"
              value={filters.min_commission}
              onChange={(e) => setFilter("min_commission", e.target.value)}
            />
          </label>
          <label>
            Max commission
            <input
              type="number"
              value={filters.max_commission}
              onChange={(e) => setFilter("max_commission", e.target.value)}
            />
          </label>
          <label>
            Calculation method
            <select
              value={filters.calculation_scope}
              onChange={(e) => setFilter("calculation_scope", e.target.value)}
            >
              <option value="all">All</option>
              <option value="order">Order</option>
              <option value="employee_month">Employee month</option>
            </select>
          </label>
        </div>
      </section>

      <CommissionSummary kpis={summary?.kpis} currency={currency} />
      <CommissionProcessStatus pipeline={summary?.pipeline} />

      {canManage ? (
        <section className="panel co-bulk">
          <div className="co-bulk__head">
            <h2 className="co-section-title">Bulk operations</h2>
            <span className="co-muted">{selectedCount} commissions selected</span>
          </div>
          <div className="co-bulk__actions">
            {(isManager || isAdmin) && (
              <button
                type="button"
                className="btn-secondary"
                disabled={actionBusy}
                onClick={() => runBulk("approve_manager")}
              >
                Manager approve
              </button>
            )}
            {(isFinance || isAdmin) && (
              <button
                type="button"
                className="btn-secondary"
                disabled={actionBusy}
                onClick={() => runBulk("approve_finance")}
              >
                Finance approve
              </button>
            )}
            {canEditAdjustments && (
              <button
                type="button"
                className="btn-secondary"
                disabled={actionBusy}
                onClick={() => runBulk("reject")}
              >
                Reject
              </button>
            )}
            {canManage && (
              <button
                type="button"
                className="btn-secondary"
                disabled={actionBusy}
                onClick={() => runBulk("assign_reviewer")}
              >
                Assign reviewer
              </button>
            )}
            {isAdmin && (
              <>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={actionBusy}
                  onClick={() => runBulk("recalculate", { force: false })}
                >
                  Recalculate selected
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={actionBusy}
                  onClick={handlePeriodRecalculate}
                >
                  Recalculate period
                </button>
              </>
            )}
            <button
              type="button"
              className="btn-secondary"
              disabled={actionBusy}
              onClick={() => handleExport("payroll", "csv")}
            >
              Export selected period
            </button>
          </div>
        </section>
      ) : (
        <div className="banner co-banner">
          <strong>Personal view:</strong> You are viewing your own commissions only.
        </div>
      )}

      {message ? <p className="co-banner co-banner--msg">{message}</p> : null}

      <CommissionGrid
        rows={rows}
        loading={loading}
        error={error}
        selected={selected}
        onToggle={toggleIds}
        onToggleAll={toggleAll}
        onOpen={openWorkspace}
        currency={currency}
      />

      {workspaceRow ? (
        <CommissionWorkspace
          detail={detail}
          loading={detailLoading}
          onClose={() => {
            setWorkspaceRow(null);
            setDetail(null);
          }}
          currency={currency}
          canEdit={canEditAdjustments}
          onCreateAdjustment={createAdjustment}
          adjustBusy={adjustBusy}
        />
      ) : null}

      {!loading && rows.length > 0 ? (
        <p className="co-footer-hint">
          Liability{" "}
          {formatMoney(summary?.kpis?.commission_liability, currency)} across{" "}
          {summary?.kpis?.record_count ?? 0} commission lines.
        </p>
      ) : null}
    </div>
  );
}
