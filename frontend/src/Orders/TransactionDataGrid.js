import { Link, useNavigate } from "react-router-dom";
import { formatMoney } from "../utils/currency";

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

function StatusBadge({ label, tone }) {
  return <span className={`tx-badge tx-badge--${tone || "neutral"}`}>{label}</span>;
}

function lifecycleTone(label) {
  const s = String(label || "").toLowerCase();
  if (s.includes("calculated") || s.includes("paid") || s.includes("approved")) return "success";
  if (s.includes("pending") || s.includes("imported")) return "warning";
  if (s.includes("fail") || s.includes("reject") || s.includes("cancel")) return "danger";
  return "neutral";
}

function commissionTone(status) {
  if (status === "calculated" || status === "paid") return "success";
  if (status === "blocked" || status === "failed") return "danger";
  return "warning";
}

function TransactionDataGrid({
  orders,
  loading,
  isAdmin,
  busy,
  selectedIds,
  onSelectionChange,
  onApprove,
  onBulkApprove,
  onBulkReject,
  onBulkCalculate,
  onBulkExport,
  onAssignRep,
}) {
  const navigate = useNavigate();
  const allSelected = orders.length > 0 && orders.every((o) => selectedIds.has(o.id));

  const toggleAll = () => {
    if (allSelected) onSelectionChange(new Set());
    else onSelectionChange(new Set(orders.map((o) => o.id)));
  };

  const toggleOne = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectionChange(next);
  };

  const canApprove = (order) => {
    if (!isAdmin) return false;
    const s = String(order.order_status || "").toLowerCase();
    return s === "booked" || s === "pending" || s === "imported";
  };

  return (
    <section className="tx-grid" aria-label="Orders">
      {selectedIds.size > 0 && isAdmin ? (
        <div className="tx-bulk" role="toolbar">
          <span>{selectedIds.size} selected</span>
          <button type="button" className="btn-secondary" disabled={busy} onClick={onBulkApprove}>
            Approve
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={onBulkReject}>
            Reject
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={onBulkCalculate}>
            Calculate Commission
          </button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={onAssignRep}>
            Assign Sales Rep
          </button>
          <button type="button" className="btn-secondary" onClick={onBulkExport}>
            Export
          </button>
          <button type="button" className="cp-btn-ghost" onClick={() => onSelectionChange(new Set())}>
            Clear
          </button>
        </div>
      ) : null}

      <div className="tx-grid__wrap">
        <table className="tx-table">
          <thead>
            <tr>
              {isAdmin ? (
                <th className="tx-table__check">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    aria-label="Select all"
                  />
                </th>
              ) : null}
              <th>Order ID</th>
              <th>Customer</th>
              <th>Product</th>
              <th>Sales Rep</th>
              <th>Sales Amount</th>
              <th>Order Date</th>
              <th>Status</th>
              <th>Commission Status</th>
              <th>Commission Amount</th>
              <th>Plan Applied</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && orders.length === 0 ? (
              <tr>
                <td colSpan={13} className="tx-table__empty">
                  Loading orders…
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={13} className="tx-table__empty">
                  No orders match your filters.
                </td>
              </tr>
            ) : (
              orders.map((order) => {
                const life = order.lifecycle_status || order.order_status;
                return (
                  <tr
                    key={order.id}
                    className="tx-table__row"
                    onClick={() => navigate(`/orders/${order.id}/overview`)}
                  >
                    {isAdmin ? (
                      <td className="tx-table__check" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(order.id)}
                          onChange={() => toggleOne(order.id)}
                          aria-label={`Select ${order.order_id}`}
                        />
                      </td>
                    ) : null}
                    <td className="tx-table__id">{order.order_id}</td>
                    <td>{order.customer || order.customer_name || "—"}</td>
                    <td>{order.product || order.product_name || order.service_name || "—"}</td>
                    <td>{order.sales_rep || order.employee_id || "—"}</td>
                    <td>{formatMoney(order.sales_amount, order.currency)}</td>
                    <td>{formatDate(order.order_date)}</td>
                    <td>
                      <StatusBadge label={life} tone={lifecycleTone(life)} />
                    </td>
                    <td>
                      <StatusBadge
                        label={order.commission_status || "pending"}
                        tone={commissionTone(order.commission_status)}
                      />
                    </td>
                    <td>
                      {order.has_commission
                        ? formatMoney(order.commission_amount, order.currency)
                        : "—"}
                    </td>
                    <td>{order.commission_plan_name || "—"}</td>
                    <td>{formatDate(order.uploaded_at)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="tx-table__actions">
                        <Link className="tx-link" to={`/orders/${order.id}/overview`}>
                          Open
                        </Link>
                        {canApprove(order) ? (
                          <button
                            type="button"
                            className="tx-link"
                            disabled={busy}
                            onClick={() => onApprove(order)}
                          >
                            Approve
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <p className="tx-grid__count">
        {loading ? "Updating…" : `${orders.length.toLocaleString()} order${orders.length === 1 ? "" : "s"}`}
      </p>
    </section>
  );
}

export default TransactionDataGrid;
