import DatePickerField from "../Components/DatePickerField";

function CompPlansToolbar({
  filters,
  onChange,
  roles = [],
  businessGroups = [],
  owners = [],
  approvers = [],
  onClear,
}) {
  return (
    <section className="cp-filters panel" aria-label="Filters and search">
      <div className="cp-section-head">
        <div>
          <h2 className="cp-section-title">Filters & search</h2>
          <p className="cp-section-hint">
            Search by plan, employee, business unit, version, or owner
          </p>
        </div>
        <button type="button" className="btn-secondary" onClick={onClear}>
          Clear all
        </button>
      </div>
      <div className="cp-catalog-toolbar" role="search">
        <label className="cp-catalog-toolbar__search">
          <span className="visually-hidden">Search plans</span>
          <input
            type="search"
            placeholder="Plan name, employee, business unit, version, owner…"
            value={filters.q}
            onChange={(e) => onChange({ ...filters, q: e.target.value })}
          />
        </label>
        <select
          aria-label="Version status"
          value={filters.version_status}
          onChange={(e) => onChange({ ...filters, version_status: e.target.value })}
        >
          <option value="">Status: All</option>
          <option value="Published">Published</option>
          <option value="Draft">Draft</option>
          <option value="Archived">Archived</option>
        </select>
        <select
          aria-label="Health / readiness"
          value={filters.health}
          onChange={(e) => onChange({ ...filters, health: e.target.value })}
        >
          <option value="">Readiness: All</option>
          <option value="healthy">Healthy</option>
          <option value="attention">Review required (all)</option>
          <option value="warning">Review Required</option>
          <option value="critical">Critical Attention</option>
        </select>
        <select
          aria-label="Plan type"
          value={filters.plan_type}
          onChange={(e) => onChange({ ...filters, plan_type: e.target.value })}
        >
          <option value="">Plan type: All</option>
          <option value="sales_commission">Sales Commission</option>
          <option value="bonus_plan">Bonus Plan</option>
          <option value="manager_override">Manager Override</option>
          <option value="channel_incentive">Channel Incentive</option>
          <option value="spiff">SPIFF</option>
        </select>
        <select
          aria-label="Role"
          value={filters.role}
          onChange={(e) => onChange({ ...filters, role: e.target.value })}
        >
          <option value="">Role: All</option>
          {roles.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
        <select
          aria-label="Business unit"
          value={filters.business_group}
          onChange={(e) => onChange({ ...filters, business_group: e.target.value })}
        >
          <option value="">Business unit: All</option>
          {businessGroups.map((bg) => (
            <option key={bg} value={bg}>
              {bg}
            </option>
          ))}
        </select>
        <select
          aria-label="Owner"
          value={filters.owner}
          onChange={(e) => onChange({ ...filters, owner: e.target.value })}
        >
          <option value="">Owner: All</option>
          {owners.map((owner) => (
            <option key={owner} value={owner}>
              {owner}
            </option>
          ))}
        </select>
        <select
          aria-label="Approver"
          value={filters.approver}
          onChange={(e) => onChange({ ...filters, approver: e.target.value })}
        >
          <option value="">Approver: All</option>
          {approvers.map((approver) => (
            <option key={approver} value={approver}>
              {approver}
            </option>
          ))}
        </select>
        <select
          aria-label="Calculation status"
          value={filters.calculation_status}
          onChange={(e) => onChange({ ...filters, calculation_status: e.target.value })}
        >
          <option value="">Calc status: All</option>
          <option value="ready">Ready for Calculation</option>
          <option value="blocked">Calculation Blocked</option>
          <option value="pending">Pending Publish</option>
        </select>
        <select
          aria-label="Approval status"
          value={filters.approval_status}
          onChange={(e) => onChange({ ...filters, approval_status: e.target.value })}
        >
          <option value="">Approval: All</option>
          <option value="published">Published</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </select>
        <select
          aria-label="Readiness score"
          value={filters.readiness_min}
          onChange={(e) => onChange({ ...filters, readiness_min: e.target.value })}
        >
          <option value="">Readiness score: All</option>
          <option value="80">80%+</option>
          <option value="60">60%+</option>
          <option value="40">40%+</option>
          <option value="0">Below 40%</option>
        </select>
        <select
          aria-label="Calculation method"
          value={filters.commission_table_type}
          onChange={(e) => onChange({ ...filters, commission_table_type: e.target.value })}
        >
          <option value="">Method: All</option>
          <option value="RATE">Rate tiers</option>
          <option value="HIGHEST">Highest rate</option>
          <option value="MARGINAL">Marginal / Progressive</option>
          <option value="FLAT">Flat rate</option>
          <option value="LOOKUP">Lookup</option>
        </select>
        <DatePickerField
          label="Effective on"
          value={filters.effective_on}
          onChange={(value) => onChange({ ...filters, effective_on: value })}
          fullWidth={false}
          className="cp-toolbar-date"
        />
      </div>
    </section>
  );
}

export default CompPlansToolbar;
