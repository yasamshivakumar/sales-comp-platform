import { useState } from "react";
import { formatMoney } from "../utils/currency";
import {
  AdjustmentManager,
  ApprovalWorkflow,
  AuditHistory,
  CalculationBreakdown,
} from "./workspaceParts";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "breakdown", label: "Calculation Breakdown" },
  { id: "transactions", label: "Transactions" },
  { id: "adjustments", label: "Adjustments" },
  { id: "approvals", label: "Approvals" },
  { id: "audit", label: "Audit History" },
];

export default function CommissionWorkspace({
  detail,
  loading,
  onClose,
  currency,
  canEdit,
  onCreateAdjustment,
  adjustBusy,
}) {
  const [tab, setTab] = useState("overview");
  const overview = detail?.overview || {};
  const cur = overview.currency || currency;

  return (
    <div className="co-modal" role="dialog" aria-modal="true" aria-label="Commission statement">
      <button type="button" className="co-modal__backdrop" onClick={onClose} aria-label="Close" />
      <div className="co-modal__panel">
        <header className="co-modal__head">
          <div>
            <p className="co-eyebrow">Commission Statement Workspace</p>
            <h2>{overview.employee_name || "Commission detail"}</h2>
            <p className="co-muted">
              {overview.employee_id} · {overview.period_label} · {overview.plan_name}
            </p>
          </div>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </header>

        {loading ? (
          <p className="co-muted">Loading statement…</p>
        ) : !detail ? (
          <p className="co-error">Unable to load commission detail.</p>
        ) : (
          <>
            <div className="co-tabs" role="tablist">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  className={`co-tabs__btn${tab === t.id ? " is-active" : ""}`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className="co-tab-body">
              {tab === "overview" ? (
                <dl className="co-dl co-dl--overview">
                  <div>
                    <dt>Employee</dt>
                    <dd>{overview.employee_name}</dd>
                  </div>
                  <div>
                    <dt>Role</dt>
                    <dd>{overview.role || "—"}</dd>
                  </div>
                  <div>
                    <dt>Territory</dt>
                    <dd>{overview.territory || "—"}</dd>
                  </div>
                  <div>
                    <dt>Sales</dt>
                    <dd>{formatMoney(overview.sales_amount, cur)}</dd>
                  </div>
                  <div>
                    <dt>Gross commission</dt>
                    <dd>{formatMoney(overview.gross_commission, cur)}</dd>
                  </div>
                  <div>
                    <dt>Adjustments</dt>
                    <dd>{formatMoney(overview.adjustments, cur)}</dd>
                  </div>
                  <div>
                    <dt>Final commission</dt>
                    <dd>
                      <strong>{formatMoney(overview.final_commission, cur)}</strong>
                    </dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{overview.status_label}</dd>
                  </div>
                  <div>
                    <dt>Transactions</dt>
                    <dd>{overview.transaction_count}</dd>
                  </div>
                  <div>
                    <dt>Reviewer</dt>
                    <dd>{overview.reviewer || "—"}</dd>
                  </div>
                </dl>
              ) : null}

              {tab === "breakdown" ? (
                <CalculationBreakdown explanations={detail.explanations} currency={cur} />
              ) : null}

              {tab === "transactions" ? (
                <div className="co-table-wrap">
                  <table className="co-table">
                    <thead>
                      <tr>
                        <th>Order ID</th>
                        <th>Customer</th>
                        <th>Product</th>
                        <th>Amount</th>
                        <th>Sales credit</th>
                        <th>Commission</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(detail.lines || []).map((line) => (
                        <tr key={line.id}>
                          <td>{line.order_id || "—"}</td>
                          <td>{line.customer}</td>
                          <td>{line.product}</td>
                          <td>{formatMoney(line.amount, line.currency || cur)}</td>
                          <td>{formatMoney(line.sales_credit, line.currency || cur)}</td>
                          <td>{formatMoney(line.commission_generated, line.currency || cur)}</td>
                          <td>{line.status_label}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {tab === "adjustments" ? (
                <AdjustmentManager
                  adjustments={detail.adjustments}
                  currency={cur}
                  canEdit={canEdit}
                  commissionIds={overview.commission_ids}
                  onCreate={onCreateAdjustment}
                  busy={adjustBusy}
                />
              ) : null}

              {tab === "approvals" ? (
                <ApprovalWorkflow approvals={detail.approvals} />
              ) : null}

              {tab === "audit" ? <AuditHistory audit={detail.audit} /> : null}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
