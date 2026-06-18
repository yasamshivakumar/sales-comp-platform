import { useEffect, useState } from "react";
import api from "../api";
import StatusPill from "../Components/StatusPill";
import CommissionSearchSelect from "../Components/CommissionSearchSelect";
import "../Components/enterprise.css";

function formatDate(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatAmount(value) {
  const amount = parseFloat(value) || 0;
  return amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function truncateIssue(text, max = 72) {
  if (!text?.trim()) return "—";
  const trimmed = text.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
}

function DisputesPanel({
  canResolve,
  prefillCommission,
  onPrefillConsumed,
  panelRef,
  employeeMode = false,
  onSubmitted,
}) {
  const [disputes, setDisputes] = useState([]);
  const [selectedCommission, setSelectedCommission] = useState(null);
  const [message, setMessage] = useState("");
  const [disputeMessage, setDisputeMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.get("disputes/");
      const data = response.data;
      setDisputes(Array.isArray(data) ? data : data?.results || []);
    } catch {
      setDisputes([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!prefillCommission) return;
    if (prefillCommission.has_open_dispute) {
      setMessage("This commission already has an open dispute.");
    } else {
      setSelectedCommission(prefillCommission);
      setMessage("");
    }
    onPrefillConsumed?.();
  }, [prefillCommission, onPrefillConsumed]);

  const submitDispute = async (e) => {
    e.preventDefault();
    if (!selectedCommission?.id || !disputeMessage.trim()) {
      setMessage("Select a commission and describe the issue.");
      return;
    }
    if (selectedCommission.has_open_dispute) {
      setMessage("This commission already has an open dispute.");
      return;
    }
    setSubmitting(true);
    setMessage("");
    try {
      await api.post("disputes/", {
        commission: selectedCommission.id,
        message: disputeMessage.trim(),
      });
      setSelectedCommission(null);
      setDisputeMessage("");
      setMessage(
        employeeMode
          ? "Dispute submitted. Your admin team will review it."
          : "Dispute submitted for review."
      );
      onSubmitted?.();
      load();
    } catch (err) {
      setMessage(
        err.response?.data?.commission?.[0] ||
          err.response?.data?.error ||
          "Submit failed."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const resolveDispute = async (disputeId, status) => {
    const resolution = window.prompt("Resolution notes (optional):", "");
    try {
      await api.post(`disputes/${disputeId}/resolve/`, {
        status,
        resolution_message: resolution || "",
      });
      setMessage(`Dispute ${status}.`);
      load();
    } catch (err) {
      setMessage(err.response?.data?.error || "Resolve failed.");
    }
  };

  const acknowledgeDispute = async (disputeId) => {
    if (
      !window.confirm(
        "Confirm you have reviewed the resolution and accept the outcome?"
      )
    ) {
      return;
    }
    try {
      await api.post(`disputes/${disputeId}/acknowledge/`);
      setMessage("Thanks — dispute acknowledged. You or admin can now remove it from the list.");
      load();
      onSubmitted?.();
    } catch (err) {
      setMessage(err.response?.data?.error || "Acknowledge failed.");
    }
  };

  const deleteDispute = async (disputeId) => {
    if (
      !window.confirm(
        "Delete this dispute record? This cannot be undone."
      )
    ) {
      return;
    }
    try {
      await api.delete(`disputes/${disputeId}/`);
      setMessage("Dispute deleted.");
      load();
      onSubmitted?.();
    } catch (err) {
      setMessage(err.response?.data?.error || "Delete failed.");
    }
  };

  const showActionsColumn = canResolve || employeeMode;
  const colCount = canResolve ? 11 : employeeMode ? 10 : 9;

  const renderActions = (d) => {
    if (canResolve && d.status === "open") {
      return (
        <>
          <button
            type="button"
            className="btn-secondary disputes-table__action-btn"
            onClick={() => resolveDispute(d.id, "resolved")}
          >
            Resolve
          </button>
          <button
            type="button"
            className="btn-secondary disputes-table__action-btn"
            onClick={() => resolveDispute(d.id, "rejected")}
          >
            Reject
          </button>
        </>
      );
    }

    if (d.can_acknowledge) {
      return (
        <button
          type="button"
          className="btn-secondary disputes-table__action-btn"
          onClick={() => acknowledgeDispute(d.id)}
        >
          Okay
        </button>
      );
    }

    if (d.can_delete) {
      return (
        <button
          type="button"
          className="btn-danger disputes-table__action-btn"
          onClick={() => deleteDispute(d.id)}
        >
          Delete
        </button>
      );
    }

    if (
      employeeMode &&
      (d.status === "resolved" || d.status === "rejected") &&
      !d.employee_acknowledged_at
    ) {
      return (
        <span className="disputes-table__hint">Awaiting your review</span>
      );
    }

    if (
      canResolve &&
      (d.status === "resolved" || d.status === "rejected") &&
      !d.employee_acknowledged_at
    ) {
      return (
        <span className="disputes-table__hint">Awaiting employee OK</span>
      );
    }

    return "—";
  };

  return (
    <div className="panel disputes-panel" style={{ marginTop: "1rem" }} ref={panelRef}>
      <div className="panel__header">
        <div>
          <h2 className="panel__title">
            {employeeMode ? "Raise a dispute" : "Dispute tracking"}
          </h2>
          <p className="disputes-panel__subtitle">
            {employeeMode ? (
              <>
                Select a commission from your statement and describe the issue. When admin
                resolves it, review the outcome and click <strong>Okay</strong> — then either
                side can delete the record.
              </>
            ) : (
              <>
                Search by order ID or employee — no commission ID needed. After you resolve
                a dispute, the employee must acknowledge before either side can delete it.
              </>
            )}
          </p>
        </div>
        {!loading && (
          <span className="disputes-panel__count">
            {disputes.length} record{disputes.length === 1 ? "" : "s"}
          </span>
        )}
      </div>

      <form className="disputes-form" onSubmit={submitDispute}>
        <div className="disputes-form__field">
          <label htmlFor="dispute-commission-search">Commission *</label>
          <CommissionSearchSelect
            selectedCommission={selectedCommission}
            onSelect={setSelectedCommission}
            disabled={submitting}
            placeholder="Search order ID, employee name, or employee ID…"
          />
        </div>

        {selectedCommission && (
          <div className="disputes-form__summary">
            <div>
              <span className="disputes-form__summary-label">Order</span>
              <strong>{selectedCommission.order_id || "—"}</strong>
            </div>
            <div>
              <span className="disputes-form__summary-label">Employee</span>
              <strong>
                {selectedCommission.employee_name || selectedCommission.employee_id || "—"}
              </strong>
            </div>
            <div>
              <span className="disputes-form__summary-label">Amount</span>
              <strong>₹{formatAmount(selectedCommission.commission_amount)}</strong>
            </div>
            <div>
              <span className="disputes-form__summary-label">Status</span>
              <StatusPill status={selectedCommission.status} compact />
            </div>
          </div>
        )}

        <div className="disputes-form__field disputes-form__field--grow">
          <label htmlFor="dispute-message">Issue description *</label>
          <textarea
            id="dispute-message"
            className="input disputes-form__textarea"
            value={disputeMessage}
            onChange={(e) => setDisputeMessage(e.target.value)}
            placeholder="Describe what is wrong with this commission…"
            rows={3}
            disabled={submitting}
          />
        </div>

        <button type="submit" className="btn-secondary" disabled={submitting}>
          {submitting ? "Submitting…" : employeeMode ? "Submit dispute" : "Open dispute"}
        </button>
      </form>

      {message && <p className="banner">{message}</p>}

      <div className="disputes-table-wrap">
        <table className="enterprise-table disputes-table">
          <thead>
            <tr>
              <th>Dispute</th>
              <th>Order</th>
              <th>Employee</th>
              <th>Amount</th>
              <th>Issue</th>
              <th>Status</th>
              {canResolve && <th>Raised by</th>}
              <th>Resolution</th>
              <th>Created</th>
              <th>Resolved</th>
              {showActionsColumn && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={colCount} className="disputes-table__state">
                  Loading disputes…
                </td>
              </tr>
            ) : disputes.length === 0 ? (
              <tr>
                <td colSpan={colCount} className="disputes-table__state">
                  {employeeMode
                    ? "No disputes yet. Use the form above to report a commission issue."
                    : "No disputes yet. Search for a commission above or use Dispute on a table row."}
                </td>
              </tr>
            ) : (
              disputes.map((d) => (
                <tr key={d.id}>
                  <td>
                    <span className="disputes-table__id">DSP-{d.id}</span>
                  </td>
                  <td>{d.order_id || "—"}</td>
                  <td>{d.employee_name || d.employee_id || "—"}</td>
                  <td>
                    {d.commission_amount != null
                      ? `₹${formatAmount(d.commission_amount)}`
                      : "—"}
                  </td>
                  <td className="disputes-table__issue" title={d.message || ""}>
                    {truncateIssue(d.message)}
                  </td>
                  <td>
                    <StatusPill status={d.status} />
                    {d.employee_acknowledged_at && (
                      <span className="disputes-table__ack" title="Employee acknowledged">
                        OK
                      </span>
                    )}
                  </td>
                  {canResolve && (
                    <td>{d.raised_by_email || "—"}</td>
                  )}
                  <td
                    className="disputes-table__issue"
                    title={d.resolution_message || ""}
                  >
                    {truncateIssue(d.resolution_message, 48)}
                  </td>
                  <td>{formatDate(d.created_at)}</td>
                  <td>{formatDate(d.resolved_at)}</td>
                  {showActionsColumn && (
                    <td className="disputes-table__actions">{renderActions(d)}</td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default DisputesPanel;
