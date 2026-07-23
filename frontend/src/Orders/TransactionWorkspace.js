import { NavLink, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import LoadingCenter from "../Components/LoadingCenter";
import { formatMoney } from "../utils/currency";

const TABS = [
  { to: "overview", label: "Overview" },
  { to: "commission", label: "Commission Calculation" },
  { to: "credit", label: "Sales Credit" },
  { to: "approvals", label: "Approvals" },
  { to: "history", label: "History" },
];

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

function OverviewTab({ order }) {
  const fields = [
    ["Order ID", order.order_id],
    ["Customer", order.customer || order.customer_name || "—"],
    ["Product", order.product || order.product_name || "—"],
    ["Service", order.service_name || "—"],
    ["Amount", formatMoney(order.sales_amount, order.currency)],
    ["Currency", order.currency || "INR"],
    ["Order Date", order.order_date],
    ["Sales Rep", order.sales_rep || order.employee_id || "—"],
    ["Region", order.region || "—"],
    ["Territory", order.territory_name || "—"],
    ["Business Unit", order.business_group || "—"],
    ["Source", order.source || order.crm_provider || "manual"],
    ["Created By", order.created_by || "—"],
    ["Lifecycle", order.lifecycle_status || order.order_status],
  ];
  return (
    <div className="tx-tab">
      <h2>Order Overview</h2>
      <dl className="tx-overview-grid">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function CommissionTab({ order }) {
  const breakdown = order.commission_breakdown || {};
  const steps = breakdown.steps || [];
  return (
    <div className="tx-tab">
      <h2>Commission Calculation</h2>
      {!breakdown.available ? (
        <p className="tx-muted">{breakdown.reason || "Not calculated yet."}</p>
      ) : (
        <>
          <div className="tx-comm-meta">
            <div>
              <span>Applied Plan</span>
              <strong>{breakdown.plan_name || order.commission_plan_name || "—"}</strong>
            </div>
            <div>
              <span>Rule</span>
              <strong>{breakdown.rule || "—"}</strong>
            </div>
            <div>
              <span>Total</span>
              <strong>{formatMoney(breakdown.total ?? order.commission_amount, order.currency)}</strong>
            </div>
          </div>
          {breakdown.note ? <p className="tx-muted">{breakdown.note}</p> : null}
          <ul className="tx-comm-steps">
            {steps.map((step) => (
              <li key={step.key || step.label}>
                <strong>{step.label}</strong>
                <span>{step.display}</span>
                {step.detail ? <em>{step.detail}</em> : null}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function CreditTab({ order, onSave, busy }) {
  const [rows, setRows] = useState(order.sales_credits || []);

  useEffect(() => {
    setRows(order.sales_credits || []);
  }, [order]);

  const update = (idx, field, value) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  };

  const addRow = () => {
    setRows((prev) => [
      ...prev,
      { employee_id: "", name: "", role: "Overlay Credit", percent: 0 },
    ]);
  };

  return (
    <div className="tx-tab">
      <h2>Sales Credit</h2>
      <p className="tx-muted">Primary, split, overlay, and manager credit allocation.</p>
      <table className="tx-credit-table">
        <thead>
          <tr>
            <th>Name / ID</th>
            <th>Role</th>
            <th>%</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`${row.employee_id}-${idx}`}>
              <td>
                <input
                  value={row.name || row.employee_id || ""}
                  onChange={(e) => {
                    update(idx, "name", e.target.value);
                    update(idx, "employee_id", e.target.value);
                  }}
                />
              </td>
              <td>
                <select
                  value={row.role || "Primary Sales Rep"}
                  onChange={(e) => update(idx, "role", e.target.value)}
                >
                  <option>Primary Sales Rep</option>
                  <option>Split Credit</option>
                  <option>Overlay Credit</option>
                  <option>Manager Credit</option>
                </select>
              </td>
              <td>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={row.percent ?? 0}
                  onChange={(e) => update(idx, "percent", Number(e.target.value))}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="tx-tab__actions">
        <button type="button" className="btn-secondary" onClick={addRow}>
          Add credit row
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={busy || order.is_locked}
          onClick={() => onSave({ sales_credits: rows })}
        >
          Save credits
        </button>
      </div>
      {order.is_locked ? (
        <p className="tx-muted">Approved orders are locked — credits are read-only.</p>
      ) : null}
    </div>
  );
}

function ApprovalsTab({ order, onApprove, busy, isAdmin }) {
  const s = String(order.order_status || "").toLowerCase();
  const pending = s === "booked" || s === "pending" || s === "imported";
  return (
    <div className="tx-tab">
      <h2>Approvals</h2>
      <p>
        Current status: <strong>{order.lifecycle_status || order.order_status}</strong>
      </p>
      <p className="tx-muted">
        Lifecycle: Imported → Pending Review → Approved → Commission Calculated → Paid
      </p>
      {isAdmin && pending ? (
        <button type="button" className="btn-primary" disabled={busy} onClick={onApprove}>
          Approve & Calculate Commission
        </button>
      ) : null}
      {order.is_locked ? (
        <p className="tx-muted">This order is locked after approval.</p>
      ) : null}
    </div>
  );
}

function HistoryTab({ order }) {
  const rows = order.audit_history || [];
  return (
    <div className="tx-tab">
      <h2>Audit History</h2>
      {rows.length === 0 ? (
        <p className="tx-muted">No audit events recorded for this order yet.</p>
      ) : (
        <ul className="tx-history">
          {rows.map((row) => (
            <li key={row.id}>
              <strong>{row.action}</strong>
              <span>{row.user}</span>
              <time>{formatDate(row.timestamp)}</time>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TransactionWorkspace() {
  const { orderId } = useParams();
  const navigate = useNavigate();
  const { error, success, warning } = useToast();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [orderRes, profileRes] = await Promise.all([
        api.get(`orders/${orderId}/`),
        api.get("user-profile/"),
      ]);
      setOrder(orderRes.data);
      setIsAdmin(Boolean(profileRes.data.is_admin));
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load order"));
      navigate("/orders");
    } finally {
      setLoading(false);
    }
  }, [orderId, error, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  const patch = async (payload) => {
    setBusy(true);
    try {
      const res = await api.patch(`orders/${orderId}/`, payload);
      setOrder(res.data);
      success("Order updated");
    } catch (err) {
      error(getApiErrorMessage(err, "Update failed"));
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    setBusy(true);
    try {
      const res = await api.patch(`orders/${orderId}/`, { order_status: "Success" });
      setOrder(res.data);
      if (res.data.has_commission) success("Approved — commission calculated");
      else warning(res.data.commission_skip_reason || "Approved — no commission yet");
    } catch (err) {
      error(getApiErrorMessage(err, "Approve failed"));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !order) return <LoadingCenter minHeight={280} />;
  if (!order) return null;

  return (
    <div className="tx-workspace">
      <div className="tx-workspace__top">
        <button type="button" className="cp-btn-ghost" onClick={() => navigate("/orders")}>
          ← Orders
        </button>
        <div>
          <h1>{order.order_id}</h1>
          <p className="tx-muted">
            {order.customer || order.customer_name || "Customer —"} ·{" "}
            {order.lifecycle_status || order.order_status} ·{" "}
            {formatMoney(order.sales_amount, order.currency)}
          </p>
        </div>
      </div>
      <div className="tx-workspace__body">
        <nav className="tx-workspace__nav" aria-label="Order sections">
          <ul>
            {TABS.map((tab) => (
              <li key={tab.to}>
                <NavLink
                  to={`/orders/${orderId}/${tab.to}`}
                  className={({ isActive }) =>
                    `tx-workspace__link${isActive ? " is-active" : ""}`
                  }
                >
                  {tab.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="tx-workspace__content">
          <Routes>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<OverviewTab order={order} />} />
            <Route path="commission" element={<CommissionTab order={order} />} />
            <Route
              path="credit"
              element={<CreditTab order={order} onSave={patch} busy={busy} />}
            />
            <Route
              path="approvals"
              element={
                <ApprovalsTab
                  order={order}
                  onApprove={approve}
                  busy={busy}
                  isAdmin={isAdmin}
                />
              }
            />
            <Route path="history" element={<HistoryTab order={order} />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

export default TransactionWorkspace;
