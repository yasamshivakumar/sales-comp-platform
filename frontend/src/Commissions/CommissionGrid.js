import { formatMoney } from "../utils/currency";
import StatusPill from "../Components/StatusPill";

export default function CommissionGrid({
  rows,
  loading,
  error,
  selected,
  onToggle,
  onToggleAll,
  onOpen,
  currency,
}) {
  const allIds = rows.flatMap((r) => r.commission_ids || []);
  const allSelected = allIds.length > 0 && allIds.every((id) => selected.has(id));

  return (
    <div className="panel co-grid-panel">
      <div className="co-grid-panel__head">
        <h2 className="co-section-title">Commission data grid</h2>
        <span className="co-muted">{rows.length} employee-period rows</span>
      </div>
      <div className="co-table-wrap">
        <table className="co-table">
          <thead>
            <tr>
              <th className="co-table__check">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() => onToggleAll(allIds)}
                  aria-label="Select all"
                />
              </th>
              <th>Employee</th>
              <th>Employee ID</th>
              <th>Role</th>
              <th>Transactions</th>
              <th>Sales</th>
              <th>Plan</th>
              <th>Period</th>
              <th>Gross</th>
              <th>Adjustments</th>
              <th>Final</th>
              <th>Status</th>
              <th>Approval</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={14} className="co-table__state">
                  Loading commission operations…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={14} className="co-table__state co-table__state--error">
                  {error}
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={14} className="co-table__state">
                  No commission rows for the selected filters.
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const ids = row.commission_ids || [];
                const checked = ids.length > 0 && ids.every((id) => selected.has(id));
                return (
                  <tr key={row.row_key} className="co-row">
                    <td className="co-table__check">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onToggle(ids)}
                        aria-label={`Select ${row.employee_name}`}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="co-link-btn"
                        onClick={() => onOpen(row)}
                      >
                        {row.employee_name}
                      </button>
                      <div className="co-sub">{row.employee_email}</div>
                    </td>
                    <td>{row.employee_id || "—"}</td>
                    <td>{row.role || "—"}</td>
                    <td>{row.transaction_count}</td>
                    <td>{formatMoney(row.sales_amount, row.currency || currency)}</td>
                    <td>{row.plan_name || "—"}</td>
                    <td>{row.period_label || "—"}</td>
                    <td>{formatMoney(row.gross_commission, row.currency || currency)}</td>
                    <td>{formatMoney(row.adjustments, row.currency || currency)}</td>
                    <td>
                      <strong>
                        {formatMoney(row.final_commission, row.currency || currency)}
                      </strong>
                    </td>
                    <td>
                      <StatusPill status={row.status_label || row.status} compact />
                      {row.has_adjustments ? (
                        <span className="co-chip">Adjusted</span>
                      ) : null}
                    </td>
                    <td className="co-cap">{(row.approval_stage || "").replace(/_/g, " ")}</td>
                    <td>
                      <button
                        type="button"
                        className="btn-secondary co-btn-sm"
                        onClick={() => onOpen(row)}
                      >
                        Review
                      </button>
                    </td>
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
