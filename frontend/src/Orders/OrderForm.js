import { useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import EmployeeSearchSelect from "../Components/EmployeeSearchSelect";
import DatePickerField from "../Components/DatePickerField";
import { CURRENCY_OPTIONS } from "../utils/currency";
import { currencyForBusinessGroup } from "../utils/businessGroups";

const INITIAL_FORM = {
  order_id: "",
  order_date: "",
  employee_id: "",
  position_name: "",
  territory: "",
  service_name: "",
  product_name: "",
  distribution: "",
  region: "",
  customer_segment: "",
  business_group: "",
  sales_amount: "",
  order_status: "Booked",
  currency: "USD",
};

const INITIAL_EMPLOYEE_META = {
  display_name: "",
  position_name: "",
  business_group: "",
  manager_name: "",
  territory_name: "",
};

function OrderForm({ onOrderCreated }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [employeeMeta, setEmployeeMeta] = useState(INITIAL_EMPLOYEE_META);
  const [saving, setSaving] = useState(false);
  const { success, error } = useToast();

  const handleChange = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value });
  };

  const handleBusinessGroupChange = (event) => {
    const businessGroup = event.target.value;
    const groupCurrency = currencyForBusinessGroup(businessGroup, "");
    setForm({
      ...form,
      business_group: businessGroup,
      currency: groupCurrency || form.currency,
    });
  };

  const handleEmployeeSelect = (employee) => {
    if (!employee) {
      setForm((prev) => ({
        ...prev,
        employee_id: "",
        position_name: "",
        business_group: "",
        territory: "",
      }));
      setEmployeeMeta(INITIAL_EMPLOYEE_META);
      return;
    }

    const groupCurrency = currencyForBusinessGroup(employee.business_group || "", "");
    setForm((prev) => ({
      ...prev,
      employee_id: employee.employee_id || "",
      position_name: employee.position_name || "",
      business_group: employee.business_group || prev.business_group || "",
      territory: employee.territory_id || "",
      currency: groupCurrency || prev.currency,
    }));
    setEmployeeMeta({
      display_name: employee.display_name || "",
      position_name: employee.position_name || "",
      business_group: employee.business_group || "",
      manager_name: employee.manager_name || "",
      territory_name: employee.territory_name || "",
    });
  };

  const resetForm = () => {
    setForm(INITIAL_FORM);
    setEmployeeMeta(INITIAL_EMPLOYEE_META);
  };

  const saveOrder = async () => {
    if (!form.order_id || !form.order_date || !form.employee_id || !form.sales_amount) {
      error("Order ID, order date, employee ID, and sales amount are required");
      return;
    }

    setSaving(true);
    try {
      const payload = { ...form };
      if (!payload.territory) {
        delete payload.territory;
      }
      await api.post("orders/", payload);
      success(
        form.order_status === "Success"
          ? "Order created — commission calculated if a plan matches"
          : "Order saved — open Order queue to mark Success when the deal closes"
      );
      resetForm();
      onOrderCreated?.();
    } catch (err) {
      error(err.response?.data?.detail || err.response?.data?.error || "Failed to create order");
    } finally {
      setSaving(false);
    }
  };

  const showEmployeeMeta = Boolean(
    form.employee_id &&
      (employeeMeta.display_name ||
        employeeMeta.position_name ||
        employeeMeta.manager_name ||
        employeeMeta.territory_name)
  );

  return (
    <div className="orders-panel">
      <div className="orders-panel__header">
        <div>
          <h2 className="orders-panel__title">Create order</h2>
          <p className="orders-panel__desc">
            Select an employee from User Setup to auto-fill position, business group, manager, and territory.
          </p>
        </div>
      </div>

      <div className="orders-form-grid">
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
          <DatePickerField
            id="order_date"
            label="Order date *"
            value={form.order_date}
            onChange={(value) => setForm({ ...form, order_date: value })}
            disabled={saving}
            required
          />
        </div>

        <div className="form-field">
          <label htmlFor="employee_id">Employee ID *</label>
          <EmployeeSearchSelect
            value={form.employee_id}
            onSelect={handleEmployeeSelect}
            disabled={saving}
            placeholder="Search EMP001 or rep name…"
          />
        </div>

        {showEmployeeMeta && (
          <div className="orders-employee-meta">
            {employeeMeta.display_name && (
              <div className="orders-employee-meta__item">
                <span className="orders-employee-meta__label">Rep</span>
                <span className="orders-employee-meta__value">{employeeMeta.display_name}</span>
              </div>
            )}
            <div className="orders-employee-meta__item">
              <span className="orders-employee-meta__label">Position</span>
              <span className="orders-employee-meta__value">
                {employeeMeta.position_name || "—"}
              </span>
            </div>
            <div className="orders-employee-meta__item">
              <span className="orders-employee-meta__label">Manager</span>
              <span className="orders-employee-meta__value">
                {employeeMeta.manager_name || "—"}
              </span>
            </div>
            <div className="orders-employee-meta__item">
              <span className="orders-employee-meta__label">Business group</span>
              <span className="orders-employee-meta__value">
                {employeeMeta.business_group || "—"}
              </span>
            </div>
            <div className="orders-employee-meta__item">
              <span className="orders-employee-meta__label">Territory</span>
              <span className="orders-employee-meta__value">
                {employeeMeta.territory_name || "—"}
              </span>
            </div>
          </div>
        )}

        <div className="form-field">
          <label htmlFor="product_name">Product name</label>
          <input
            id="product_name"
            name="product_name"
            value={form.product_name}
            onChange={handleChange}
            placeholder="Enterprise Suite"
          />
        </div>

        <div className="form-field">
          <label htmlFor="service_name">Service</label>
          <input
            id="service_name"
            name="service_name"
            value={form.service_name}
            onChange={handleChange}
            placeholder="Subscription"
          />
        </div>

        <div className="form-field">
          <label htmlFor="distribution">Distribution</label>
          <input
            id="distribution"
            name="distribution"
            value={form.distribution}
            onChange={handleChange}
            placeholder="Direct, Partner, etc."
          />
        </div>

        <div className="form-field">
          <label htmlFor="region">Region</label>
          <input
            id="region"
            name="region"
            value={form.region}
            onChange={handleChange}
            placeholder="West"
          />
        </div>

        <div className="form-field">
          <label htmlFor="customer_segment">Customer segment</label>
          <input
            id="customer_segment"
            name="customer_segment"
            value={form.customer_segment}
            onChange={handleChange}
            placeholder="Enterprise"
          />
        </div>

        <div className="form-field">
          <label htmlFor="business_group">Business group</label>
          <input
            id="business_group"
            name="business_group"
            value={form.business_group}
            onChange={handleBusinessGroupChange}
            placeholder="USA"
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
            <option>Success</option>
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
            {CURRENCY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="orders-form-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={saveOrder}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save order"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={resetForm}
            disabled={saving}
          >
            Clear form
          </button>
        </div>
      </div>
    </div>
  );
}

export default OrderForm;
