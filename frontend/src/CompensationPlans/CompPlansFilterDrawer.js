/**
 * Enterprise filter drawer for Compensation Operations Center
 */
function CompPlansFilterDrawer({
  open,
  onClose,
  filters,
  onChange,
  onClear,
  roles = [],
  businessGroups = [],
  owners = [],
  approvers = [],
}) {
  if (!open) return null;

  const set = (key, value) => onChange({ ...filters, [key]: value });

  return (
    <div className="cp-filter-drawer" role="dialog" aria-modal="true" aria-label="Filters">
      <button type="button" className="cp-filter-drawer__backdrop" aria-label="Close filters" onClick={onClose} />
      <aside className="cp-filter-drawer__panel">
        <div className="cp-filter-drawer__head">
          <h2>Filters</h2>
          <button type="button" className="cp-btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="cp-filter-drawer__body">
          <label>
            Status
            <select value={filters.version_status} onChange={(e) => set("version_status", e.target.value)}>
              <option value="">All</option>
              <option value="Published">Active</option>
              <option value="Draft">Draft</option>
              <option value="Archived">Expired / Archived</option>
            </select>
          </label>

          <label>
            Health
            <select value={filters.health} onChange={(e) => set("health", e.target.value)}>
              <option value="">All</option>
              <option value="healthy">Healthy</option>
              <option value="warning">Review Required</option>
              <option value="critical">Critical</option>
              <option value="attention">Needs Attention</option>
            </select>
          </label>

          <label>
            Calculation Status
            <select
              value={filters.calculation_status}
              onChange={(e) => set("calculation_status", e.target.value)}
            >
              <option value="">All</option>
              <option value="ready">Ready</option>
              <option value="blocked">Blocked</option>
              <option value="pending">Pending</option>
            </select>
          </label>

          <label>
            Plan Type
            <select value={filters.plan_type} onChange={(e) => set("plan_type", e.target.value)}>
              <option value="">All</option>
              <option value="sales_commission">Sales Commission</option>
              <option value="bonus_plan">Bonus Plan</option>
              <option value="manager_override">Manager Override</option>
              <option value="channel_incentive">Channel Incentive</option>
              <option value="spiff">SPIFF</option>
            </select>
          </label>

          <label>
            Role
            <select value={filters.role} onChange={(e) => set("role", e.target.value)}>
              <option value="">All</option>
              {roles.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </label>

          <label>
            Business Unit
            <select
              value={filters.business_group}
              onChange={(e) => set("business_group", e.target.value)}
            >
              <option value="">All</option>
              {businessGroups.map((bg) => (
                <option key={bg} value={bg}>
                  {bg}
                </option>
              ))}
            </select>
          </label>

          <label>
            Owner
            <select value={filters.owner} onChange={(e) => set("owner", e.target.value)}>
              <option value="">All</option>
              {owners.map((owner) => (
                <option key={owner} value={owner}>
                  {owner}
                </option>
              ))}
            </select>
          </label>

          <label>
            Approver
            <select value={filters.approver} onChange={(e) => set("approver", e.target.value)}>
              <option value="">All</option>
              {approvers.map((approver) => (
                <option key={approver} value={approver}>
                  {approver}
                </option>
              ))}
            </select>
          </label>

          <label>
            Effective Date
            <input
              type="date"
              value={filters.effective_on}
              onChange={(e) => set("effective_on", e.target.value)}
            />
          </label>

          <label>
            Readiness Score
            <select value={filters.readiness_min} onChange={(e) => set("readiness_min", e.target.value)}>
              <option value="">All</option>
              <option value="80">80% and above</option>
              <option value="60">60% and above</option>
              <option value="40">40% and above</option>
              <option value="0">Below 40%</option>
            </select>
          </label>

          <label>
            Min. Employees
            <input
              type="number"
              min="0"
              placeholder="e.g. 10"
              value={filters.employees_min || ""}
              onChange={(e) => set("employees_min", e.target.value)}
            />
          </label>
        </div>

        <div className="cp-filter-drawer__foot">
          <button type="button" className="btn-secondary" onClick={onClear}>
            Clear all
          </button>
          <button type="button" className="btn-primary" onClick={onClose}>
            Apply
          </button>
        </div>
      </aside>
    </div>
  );
}

export default CompPlansFilterDrawer;
