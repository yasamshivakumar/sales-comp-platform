import DatePickerField from "../Components/DatePickerField";

function TransactionFilterDrawer({ open, onClose, filters, onChange, onClear }) {
  if (!open) return null;
  const set = (key, value) => onChange({ ...filters, [key]: value });

  return (
    <div className="tx-filter-drawer" role="dialog" aria-modal="true" aria-label="Filters">
      <button type="button" className="tx-filter-drawer__backdrop" onClick={onClose} aria-label="Close" />
      <aside className="tx-filter-drawer__panel">
        <div className="tx-filter-drawer__head">
          <h2>Filters</h2>
          <button type="button" className="cp-btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="tx-filter-drawer__body">
          <label>
            Status
            <select value={filters.order_status} onChange={(e) => set("order_status", e.target.value)}>
              <option value="">All</option>
              <option value="Imported">Imported</option>
              <option value="Booked">Pending Review</option>
              <option value="Success">Approved</option>
              <option value="Rejected">Rejected</option>
              <option value="Cancelled">Cancelled</option>
              <option value="Failed">Failed</option>
            </select>
          </label>
          <label>
            Commission Status
            <select
              value={filters.commission_status}
              onChange={(e) => set("commission_status", e.target.value)}
            >
              <option value="">All</option>
              <option value="pending">Pending</option>
              <option value="calculated">Calculated</option>
              <option value="blocked">Blocked</option>
              <option value="failed">Failed</option>
              <option value="paid">Paid</option>
            </select>
          </label>
          <label>
            Sales Rep
            <input
              value={filters.sales_rep}
              onChange={(e) => set("sales_rep", e.target.value)}
              placeholder="Employee ID"
            />
          </label>
          <label>
            Customer
            <input value={filters.customer} onChange={(e) => set("customer", e.target.value)} />
          </label>
          <label>
            Product
            <input value={filters.product} onChange={(e) => set("product", e.target.value)} />
          </label>
          <label>
            Region
            <input value={filters.region} onChange={(e) => set("region", e.target.value)} />
          </label>
          <label>
            Business Unit
            <input
              value={filters.business_group}
              onChange={(e) => set("business_group", e.target.value)}
            />
          </label>
          <label>
            Import Source
            <select value={filters.source} onChange={(e) => set("source", e.target.value)}>
              <option value="">All</option>
              <option value="manual">Manual</option>
              <option value="csv">CSV</option>
              <option value="crm">CRM</option>
            </select>
          </label>
          <label>
            Date from
            <DatePickerField
              label="Date from"
              hideLabel
              value={filters.date_from}
              onChange={(value) => set("date_from", value)}
              maxDate={filters.date_to || undefined}
            />
          </label>
          <label>
            Date to
            <DatePickerField
              label="Date to"
              hideLabel
              value={filters.date_to}
              onChange={(value) => set("date_to", value)}
              minDate={filters.date_from || undefined}
            />
          </label>
          <label>
            Amount min
            <input
              type="number"
              value={filters.amount_min}
              onChange={(e) => set("amount_min", e.target.value)}
            />
          </label>
          <label>
            Amount max
            <input
              type="number"
              value={filters.amount_max}
              onChange={(e) => set("amount_max", e.target.value)}
            />
          </label>
        </div>
        <div className="tx-filter-drawer__foot">
          <button type="button" className="btn-secondary" onClick={onClear}>
            Clear
          </button>
          <button type="button" className="btn-primary" onClick={onClose}>
            Apply
          </button>
        </div>
      </aside>
    </div>
  );
}

export default TransactionFilterDrawer;
