import RefreshIcon from "@mui/icons-material/Refresh";

const SORT_OPTIONS = [
  { value: "name", label: "Name A–Z" },
  { value: "-name", label: "Name Z–A" },
  { value: "employee_id", label: "Employee ID" },
  { value: "role", label: "Role" },
  { value: "status", label: "Status" },
  { value: "-last_login", label: "Last login" },
];

/**
 * Left/right enterprise toolbar shell for People directory.
 */
export default function EnterpriseToolbar({
  search,
  onSearchChange,
  filterCount,
  onOpenFilters,
  viewId,
  views,
  onViewChange,
  ordering,
  onOrderingChange,
  columnPicker,
  onRefresh,
  refreshing,
  bulkDisabled,
  bulkLabel,
  onBulkClick,
  createSlot,
  overflowSlot,
}) {
  return (
    <div className="pe-toolbar pe-toolbar--enterprise">
      <div className="pe-toolbar__left">
        <input
          type="search"
          className="pe-toolbar__search"
          placeholder="Search name, employee ID, email, territory, manager, plan…"
          value={search}
          onChange={(e) => onSearchChange?.(e.target.value)}
          aria-label="Search employees"
        />
        <button type="button" className="btn-secondary" onClick={onOpenFilters}>
          Filter{filterCount ? ` (${filterCount})` : ""}
        </button>
        <select
          className="pe-views__select"
          value={viewId}
          onChange={(e) => onViewChange?.(e.target.value)}
          aria-label="Saved view"
        >
          {(views || []).map((view) => (
            <option key={view.id} value={view.id}>
              {view.label}
            </option>
          ))}
        </select>
        {columnPicker}
        <select
          className="pe-views__select"
          value={ordering}
          onChange={(e) => onOrderingChange?.(e.target.value)}
          aria-label="Sort"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              Sort: {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div className="pe-toolbar__right">
        <button
          type="button"
          className="btn-secondary pe-toolbar__icon-btn"
          onClick={onRefresh}
          disabled={refreshing}
          title="Refresh"
          aria-label="Refresh"
        >
          <RefreshIcon fontSize="small" />
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={bulkDisabled}
          title={bulkDisabled ? "Select rows for bulk actions" : bulkLabel}
          onClick={onBulkClick}
        >
          {bulkLabel}
        </button>
        <div className="pe-header__cta-group">
          {createSlot}
          {overflowSlot}
        </div>
      </div>
    </div>
  );
}
