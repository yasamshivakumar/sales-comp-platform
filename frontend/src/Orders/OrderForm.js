import { useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";

const INITIAL_FORM = {
  order_id: "",
  order_date: "",
  employee_id: "",
  position_name: "",
  service_name: "",
  sales_amount: "",
  order_status: "Booked",
  currency: "INR",
};

function OrderForm() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const { success, error } = useToast();

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const saveOrder = async () => {
    if (!form.order_id || !form.order_date || !form.employee_id || !form.sales_amount) {
      error("Order ID, order date, employee ID, and sales amount are required");
      return;
    }

    setSaving(true);
    try {
      await api.post("orders/", form);
      success("Order created — commission calculated if a plan matches");
      setForm(INITIAL_FORM);
    } catch (err) {
      error(err.response?.data?.detail || err.response?.data?.error || "Failed to create order");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel">
      <div className="orders-section__head">
        <div className="orders-section__icon">✏️</div>
      </div>

      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="order_id">Order ID *</label>
          <input
            id="order_id"
            name="order_id"
            value={form.order_id}
            onChange={handleChange}
            placeholder="ORD-001"
          />
        </div>

        <div className="form-field">
          <label htmlFor="order_date">Order date *</label>
          <input
            id="order_date"
            type="date"
            name="order_date"
            value={form.order_date}
            onChange={handleChange}
          />
        </div>

        <div className="form-field">
          <label htmlFor="employee_id">Employee ID *</label>
          <input
            id="employee_id"
            name="employee_id"
            value={form.employee_id}
            onChange={handleChange}
            placeholder="EMP001"
          />
        </div>

        <div className="form-field">
          <label htmlFor="position_name">Position name</label>
          <input
            id="position_name"
            name="position_name"
            value={form.position_name}
            onChange={handleChange}
            placeholder="Enterprise AE"
          />
        </div>

        <div className="form-field">
          <label htmlFor="service_name">Service</label>
          <input
            id="service_name"
            name="service_name"
            value={form.service_name}
            onChange={handleChange}
            placeholder="Consulting"
          />
        </div>

        <div className="form-field">
          <label htmlFor="sales_amount">Sales amount *</label>
          <input
            id="sales_amount"
            type="number"
            name="sales_amount"
            value={form.sales_amount}
            onChange={handleChange}
            placeholder="50000"
            min="0"
          />
        </div>

        <div className="form-field">
          <label htmlFor="order_status">Status</label>
          <select
            id="order_status"
            name="order_status"
            value={form.order_status}
            onChange={handleChange}
          >
            <option>Booked</option>
            <option>Pending</option>
            <option>Cancelled</option>
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="currency">Currency</label>
          <select
            id="currency"
            name="currency"
            value={form.currency}
            onChange={handleChange}
          >
            <option>INR</option>
            <option>USD</option>
            <option>EUR</option>
          </select>
        </div>

        <div className="form-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={saveOrder}
            disabled={saving}
          >
            {saving ? "Saving…" : "Create order"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default OrderForm;
