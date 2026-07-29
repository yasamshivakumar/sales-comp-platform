/**
 * Floating bulk action bar for Participant Management.
 * Actions map to existing /api/user-setup/bulk/ endpoints only.
 */
export default function BulkActionBar({
  count,
  busy,
  onAssignPlan,
  onUpdateQuota,
  onDeactivate,
  onExport,
  onClear,
}) {
  if (!count) return null;
  return (
    <div className="pe-bulk pe-bulk--float" role="toolbar" aria-label="Bulk actions">
      <span className="pe-bulk__count">{count} selected</span>
      <button type="button" className="btn-secondary" disabled={busy} onClick={onAssignPlan}>
        Assign Compensation Plan
      </button>
      <button type="button" className="btn-secondary" disabled={busy} onClick={onUpdateQuota}>
        Update Quota
      </button>
      <button type="button" className="btn-secondary" disabled={busy} onClick={onDeactivate}>
        Deactivate
      </button>
      <button type="button" className="btn-secondary" disabled={busy} onClick={onExport}>
        Export
      </button>
      <button type="button" className="cp-btn-ghost" onClick={onClear}>
        Clear
      </button>
    </div>
  );
}
