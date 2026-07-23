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
  customer_name: "",
  distribution: "",
  region: "",
  customer_segment: "",
  business_group: "",
  sales_amount: "",
  order_status: "Booked",
  currency: "USD",
  source: "manual",
};

const PROFILE_DISPLAY_FIELDS = [
  { key: "display_name", label: "Employee name" },
  { key: "email", label: "Email" },
  { key: "role", label: "Role" },
  { key: "title", label: "Title" },
  { key: "position_title", label: "Position title" },
  { key: "manager_name", label: "Manager" },
  { key: "manager_employee_id", label: "Manager employee ID" },
  { key: "function_name", label: "Function" },
  { key: "level", label: "Level" },
  { key: "market", label: "Market" },
  { key: "hierarchy", label: "Hierarchy" },
  { key: "hire_date", label: "Hire date" },
  { key: "personal_target", label: "Personal target" },
  { key: "pay_period_type", label: "Pay period" },
];

function OrderForm({ onOrderCreated }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [profileDetail, setProfileDetail] = useState(null);
  const [profileLocked, setProfileLocked] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [saving, setSaving] = useState(false);
  const { success, error } = useToast();

  const handleChange = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value });
  };

  const applyProfileToForm = (profile) => {
    const groupCurrency = currencyForBusinessGroup(profile.business_group || "", "");
    setForm((prev) => ({
      ...prev,
      employee_id: profile.employee_id || "",
      position_name: profile.position_name || "",
      business_group: profile.business_group || "",
      territory: profile.territory_id ? String(profile.territory_id) : "",
      region: profile.region || profile.market || "",
      currency: profile.personal_currency || groupCurrency || prev.currency,
    }));
    setProfileDetail(profile);
    setProfileLocked(true);
  };

  const handleEmployeeSelect = async (employee) => {
    if (!employee) {
      setForm((prev) => ({
        ...prev,
        employee_id: "",
        position_name: "",
        business_group: "",
        territory: "",
        region: "",
      }));
      setProfileDetail(null);
      setProfileLocked(false);
      return;
    }

    if (!employee.id) {
      setForm((prev) => ({
        ...prev,
        employee_id: employee.employee_id || "",
        position_name: "",
        business_group: "",
        territory: "",
        region: "",
      }));
      setProfileDetail(null);
      setProfileLocked(false);
      return;
    }

    setLoadingProfile(true);
    try {
      const res = await api.get(`users/${employee.id}/`);
      applyProfileToForm(res.data);
    } catch (err) {
      setProfileDetail(null);
      setProfileLocked(false);
      const groupCurrency = currencyForBusinessGroup(employee.business_group || "", "");
      setForm((prev) => ({
        ...prev,
        employee_id: employee.employee_id || "",
        position_name: employee.position_name || "",
        business_group: employee.business_group || prev.business_group || "",
        territory: employee.territory_id ? String(employee.territory_id) : "",
        region: employee.market || employee.region || "",
        currency: groupCurrency || prev.currency,
      }));
      error(
        err.response?.data?.error ||
          "Could not load full employee profile. Basic fields were filled from search."
      );
    } finally {
      setLoadingProfile(false);
    }
  };

  const resetForm = () => {
    setForm(INITIAL_FORM);
    setProfileDetail(null);
    setProfileLocked(false);
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

  const importedInputProps = profileLocked
    ? { readOnly: true, className: "form-field__input form-field__input--readonly" }
    : {};

  return (
    <div className="orders-panel">
      <div className="orders-panel__header">
        <div>
          <h2 className="orders-panel__title">Create order</h2>
          <p className="orders-panel__desc">
            Select an employee to auto-fill imported profile fields. Order details remain editable.
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
          <label htmlFor="employee_id">Employee *</label>
          <EmployeeSearchSelect
            value={form.employee_id}
            onSelect={handleEmployeeSelect}
            disabled={saving || loadingProfile}
            placeholder="Search EMP001 or rep name…"
          />
          {loadingProfile && (
            <p className="orders-form-hint">Loading employee profile…</p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="position_name">Position</label>
          <input
            id="position_name"
            name="position_name"
            value={form.position_name}
            onChange={handleChange}
            placeholder="Account Executive"
            {...importedInputProps}
          />
        </div>

        <div className="form-field">
          <label htmlFor="business_group">Business group</label>
          <input
            id="business_group"
            name="business_group"
            value={form.business_group}
            onChange={handleChange}
            placeholder="USA"
            {...importedInputProps}
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
            {...importedInputProps}
          />
        </div>

        <div className="form-field">
          <label htmlFor="currency">Currency</label>
          <select
            id="currency"
            name="currency"
            value={form.currency}
            onChange={handleChange}
            disabled={profileLocked}
            className={profileLocked ? "form-field__input--readonly" : undefined}
          >
            {CURRENCY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {profileDetail && (
          <div className="orders-employee-meta orders-employee-meta--profile">
            <p className="orders-employee-meta__title">Imported employee profile</p>
            <div className="orders-employee-meta__grid">
              {PROFILE_DISPLAY_FIELDS.map(({ key, label }) => {
                const value = profileDetail[key];
                if (!value) return null;
                return (
                  <div key={key} className="orders-employee-meta__item">
                    <span className="orders-employee-meta__label">{label}</span>
                    <span className="orders-employee-meta__value">{value}</span>
                  </div>
                );
              })}
              {profileDetail.territory_name && (
                <div className="orders-employee-meta__item">
                  <span className="orders-employee-meta__label">Territory</span>
                  <span className="orders-employee-meta__value">
                    {profileDetail.territory_name}
                    {profileDetail.territory_code
                      ? ` (${profileDetail.territory_code})`
                      : ""}
                  </span>
                </div>
              )}
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
          <label htmlFor="customer_name">Customer</label>
          <input
            id="customer_name"
            name="customer_name"
            value={form.customer_name}
            onChange={handleChange}
            placeholder="ABC Corporation"
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

        <div className="orders-form-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={saveOrder}
            disabled={saving || loadingProfile}
          >
            {saving ? "Saving…" : "Save order"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={resetForm}
            disabled={saving || loadingProfile}
          >
            Clear form
          </button>
        </div>
      </div>
    </div>
  );
}

export default OrderForm;
