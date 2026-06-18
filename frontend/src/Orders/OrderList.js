import { useCallback, useEffect, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import SearchBar from "../Components/SearchBar";
import StatusPill from "../Components/StatusPill";

const STATUS_FILTERS = [
  { id: "booked", label: "Booked", param: "Booked" },
  { id: "all", label: "All orders", param: "" },
  { id: "success", label: "Success", param: "Success" },
];

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

function formatAmount(value) {
  const amount = parseFloat(value) || 0;
  return amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function normalizeStatus(status) {
  return String(status || "").trim().toLowerCase();
}

function orderStatusPill(status) {
  const key = normalizeStatus(status);
  if (key === "success") {
    return <StatusPill status="approved" label="Success" compact />;
  }
  if (key === "booked") {
    return <StatusPill status="draft" label="Booked" compact />;
  }
  if (key === "cancelled") {
    return <StatusPill status="rejected" label="Cancelled" compact />;
  }
  return <StatusPill status="open" label={status || "Pending"} compact />;
}

function SuccessToggle({ checked, disabled, loading, onChange }) {
  return (
    <label
      className={`orders-success-toggle${disabled || loading ? " orders-success-toggle--disabled" : ""}`}
    >
      <input
        type="checkbox"
        className="orders-success-toggle__input"
        checked={checked}
        disabled={disabled || loading}
        onChange={(event) => onChange(event.target.checked)}
        aria-label={checked ? "Mark order as Booked" : "Mark order as Success"}
      />
      <span className="orders-success-toggle__track" aria-hidden="true">
        <span className="orders-success-toggle__thumb" />
      </span>
      <span className="orders-success-toggle__label">{checked ? "Success" : "Booked"}</span>
    </label>
  );
}

function OrderList({ refreshKey = 0 }) {
  const { success, error, warning } = useToast();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("booked");
  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      const query = appliedSearch.trim();
      if (query) {
        params.q = query;
      } else {
        const filter = STATUS_FILTERS.find((item) => item.id === statusFilter);
        if (filter?.param) {
          params.order_status = filter.param;
        }
      }

      const [ordersRes, profileRes] = await Promise.all([
        api.get("orders/", { params }),
        api.get("user-profile/"),
      ]);
      setOrders(Array.isArray(ordersRes.data) ? ordersRes.data : ordersRes.data.results || []);
      setIsAdmin(Boolean(profileRes.data.is_admin));
    } catch (err) {
      error(err.response?.data?.detail || "Failed to load orders");
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, appliedSearch, error]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders, refreshKey]);

  const handleSearch = () => {
    setAppliedSearch(searchInput.trim());
  };

  const handleClearSearch = () => {
    setSearchInput("");
    setAppliedSearch("");
  };

  const handleSearchKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSearch();
    }
  };

  const toggleSuccess = async (order, markSuccess) => {
    const nextStatus = markSuccess ? "Success" : "Booked";
    setUpdatingId(order.id);
    try {
      const response = await api.patch(`orders/${order.id}/`, {
        order_status: nextStatus,
      });
      const updated = response.data;
      setOrders((current) =>
        current.map((row) => (row.id === order.id ? { ...row, ...updated } : row))
      );
      if (markSuccess) {
        if (updated.has_commission) {
          success(
            `Order ${order.order_id} marked Success — commission ₹${formatAmount(updated.commission_amount)} calculated`
          );
        } else {
          warning(
            `Order ${order.order_id} marked Success — no commission yet (check User Setup + compensation plan)`
          );
        }
      } else {
        success(`Order ${order.order_id} moved back to Booked — commission removed`);
      }
    } catch (err) {
      error(err.response?.data?.detail || `Failed to update order ${order.order_id}`);
    } finally {
      setUpdatingId(null);
    }
  };

  const canToggle = (order) => {
    if (!isAdmin) return false;
    const status = normalizeStatus(order.order_status);
    return status === "booked" || status === "success" || status === "pending";
  };

  const emptyMessage = () => {
    if (appliedSearch) {
      return (
        <>
          No orders match <strong>{appliedSearch}</strong>. The order may not have imported
          successfully — check the import result for row errors, or try <strong>All orders</strong>{" "}
          after clearing search.
        </>
      );
    }
    if (statusFilter === "booked") {
      return "No booked orders — create or import orders with status Booked.";
    }
    return "No orders found for this filter.";
  };

  const columnCount = isAdmin ? 8 : 7;

  return (
    <div className="orders-panel orders-list-panel">
      <div className="orders-panel__header">
        <div>
          <h2 className="orders-panel__title">Order queue</h2>
          <p className="orders-panel__desc">
            Booked orders appear here until an admin marks them Success. Commission is calculated
            automatically when you turn Success on.
          </p>
        </div>
        {!loading && (
          <span className="orders-result-count">
            {orders.length} order{orders.length === 1 ? "" : "s"}
            {appliedSearch ? ` matching "${appliedSearch}"` : ""}
          </span>
        )}
      </div>

      <div className="orders-list-toolbar">
        <div className="orders-list-filters" role="tablist" aria-label="Order status filters">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.id}
              type="button"
              role="tab"
              aria-selected={!appliedSearch && statusFilter === filter.id}
              className={`orders-list-filter${!appliedSearch && statusFilter === filter.id ? " orders-list-filter--active" : ""}`}
              onClick={() => {
                setStatusFilter(filter.id);
                if (appliedSearch) {
                  setAppliedSearch("");
                  setSearchInput("");
                }
              }}
              disabled={Boolean(appliedSearch)}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <div className="orders-list-search">
          <SearchBar
            className="orders-list-search__bar"
            placeholder="Search order ID, employee, product…"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={handleSearchKeyDown}
          />
          <button
            type="button"
            className="btn-primary orders-list-search__btn"
            onClick={handleSearch}
            disabled={loading}
          >
            Search
          </button>
          {appliedSearch ? (
            <button
              type="button"
              className="btn-secondary orders-list-search__btn"
              onClick={handleClearSearch}
            >
              Clear
            </button>
          ) : null}
          <button
            type="button"
            className="btn-secondary orders-list-search__btn"
            onClick={loadOrders}
            disabled={loading}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </div>

      {appliedSearch ? (
        <p className="orders-list-search-hint">
          Searching all orders for <strong>{appliedSearch}</strong> (ignores Booked / Success
          filter). Clear search to return to the status tabs.
        </p>
      ) : null}

      <div className="orders-list-table-wrap">
        <table className="orders-list-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Date</th>
              <th>Employee</th>
              <th>Product / service</th>
              <th className="orders-list-table__num">Sales amount</th>
              <th>Status</th>
              <th className="orders-list-table__num">Commission</th>
              {isAdmin ? <th className="orders-list-table__toggle">Mark Success</th> : null}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columnCount} className="orders-list-empty">
                  Loading orders…
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={columnCount} className="orders-list-empty">
                  {emptyMessage()}
                </td>
              </tr>
            ) : (
              orders.map((order) => {
                const isSuccess = normalizeStatus(order.order_status) === "success";
                const toggleEnabled = canToggle(order);
                return (
                  <tr key={order.id}>
                    <td className="orders-list-id">{order.order_id}</td>
                    <td className="orders-list-date">{formatDate(order.order_date)}</td>
                    <td>{order.employee_id || "—"}</td>
                    <td className="orders-list-product">
                      {order.product_name || order.service_name || "—"}
                    </td>
                    <td className="orders-list-amount">₹{formatAmount(order.sales_amount)}</td>
                    <td className="orders-list-status">{orderStatusPill(order.order_status)}</td>
                    <td className="orders-list-commission-cell">
                      {order.has_commission ? (
                        <span className="orders-list-commission">
                          ₹{formatAmount(order.commission_amount)}
                        </span>
                      ) : (
                        <span className="orders-list-muted">—</span>
                      )}
                    </td>
                    {isAdmin ? (
                      <td className="orders-list-toggle-cell">
                        {toggleEnabled ? (
                          <SuccessToggle
                            checked={isSuccess}
                            loading={updatingId === order.id}
                            disabled={normalizeStatus(order.order_status) === "cancelled"}
                            onChange={(checked) => toggleSuccess(order, checked)}
                          />
                        ) : (
                          <span className="orders-list-muted">—</span>
                        )}
                      </td>
                    ) : null}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default OrderList;
