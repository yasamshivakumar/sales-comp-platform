import { useState } from "react";
import { formatMoney } from "../utils/currency";

export function CalculationBreakdown({ explanations, currency }) {
  if (!explanations?.length) {
    return <p className="co-muted">No calculation breakdown available.</p>;
  }

  return (
    <div className="co-breakdown">
      {explanations.map((item) => {
        const exp = item.explanation || {};
        const summary = exp.summary || {};
        const tiers = exp.tier_lines || exp.breakdown || exp.tiers || [];
        return (
          <article key={item.commission_id} className="co-breakdown__card">
            <header>
              <h4>Commission #{item.commission_id}</h4>
              {item.error ? <p className="co-error">{item.error}</p> : null}
            </header>
            <dl className="co-dl">
              <div>
                <dt>Plan</dt>
                <dd>{summary.plan_name || exp.plan_name || "—"}</dd>
              </div>
              <div>
                <dt>Sales</dt>
                <dd>
                  {formatMoney(summary.sales_amount ?? exp.sales_amount, currency)}
                </dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>
                  {formatMoney(
                    summary.commission_amount ?? exp.commission_amount,
                    currency
                  )}
                </dd>
              </div>
            </dl>
            {Array.isArray(tiers) && tiers.length > 0 ? (
              <ul className="co-tier-list">
                {tiers.map((tier, idx) => (
                  <li key={idx}>
                    <span>
                      {tier.tier_name || tier.label || `Tier ${idx + 1}`}
                      {tier.rate_pct != null ? ` · ${tier.rate_pct}%` : ""}
                      {tier.description ? ` — ${tier.description}` : ""}
                    </span>
                    <strong>
                      {formatMoney(tier.amount ?? tier.commission ?? tier.base, currency)}
                    </strong>
                  </li>
                ))}
              </ul>
            ) : exp.narrative || exp.plain_english ? (
              <p className="co-narrative">{exp.narrative || exp.plain_english}</p>
            ) : (
              <p className="co-muted">See transactions tab for line-level amounts.</p>
            )}
          </article>
        );
      })}
    </div>
  );
}

export function AdjustmentManager({
  adjustments,
  currency,
  canEdit,
  commissionIds,
  onCreate,
  busy,
}) {
  const [form, setForm] = useState({
    commission_id: "",
    adjustment_type: "manual",
    amount: "",
    reason: "",
  });

  return (
    <div className="co-adjust">
      {canEdit && commissionIds?.length ? (
        <form
          className="co-adjust__form"
          onSubmit={(e) => {
            e.preventDefault();
            onCreate({
              commission_id: Number(form.commission_id || commissionIds[0]),
              adjustment_type: form.adjustment_type,
              amount: form.amount,
              reason: form.reason,
            });
          }}
        >
          <h4>Add adjustment</h4>
          <div className="co-adjust__grid">
            <label>
              Commission
              <select
                value={form.commission_id || commissionIds[0]}
                onChange={(e) => setForm({ ...form, commission_id: e.target.value })}
              >
                {commissionIds.map((id) => (
                  <option key={id} value={id}>
                    #{id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Type
              <select
                value={form.adjustment_type}
                onChange={(e) => setForm({ ...form, adjustment_type: e.target.value })}
              >
                <option value="manual">Manual</option>
                <option value="bonus">Bonus</option>
                <option value="correction">Correction</option>
                <option value="clawback">Clawback</option>
              </select>
            </label>
            <label>
              Amount
              <input
                type="number"
                step="0.01"
                required
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </label>
            <label className="co-adjust__reason">
              Reason (required)
              <input
                type="text"
                required
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
              />
            </label>
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Post adjustment"}
          </button>
        </form>
      ) : null}

      {!adjustments?.length ? (
        <p className="co-muted">No adjustments posted.</p>
      ) : (
        <table className="co-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Amount</th>
              <th>Reason</th>
              <th>Created by</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {adjustments.map((a) => (
              <tr key={a.id}>
                <td className="co-cap">{a.adjustment_type}</td>
                <td>{formatMoney(a.amount, currency)}</td>
                <td>{a.reason}</td>
                <td>{a.created_by || "—"}</td>
                <td>{a.created_at ? new Date(a.created_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function ApprovalWorkflow({ approvals }) {
  if (!approvals?.length) {
    return <p className="co-muted">No approval events yet.</p>;
  }
  return (
    <ol className="co-timeline">
      {approvals.map((a, idx) => (
        <li key={`${a.commission_id}-${a.stage}-${idx}`}>
          <strong>{a.stage}</strong>
          <span className="co-muted">
            {a.approver || "—"}
            {a.date ? ` · ${new Date(a.date).toLocaleString()}` : ""}
          </span>
          {a.comments ? <p>{a.comments}</p> : null}
        </li>
      ))}
    </ol>
  );
}

export function AuditHistory({ audit }) {
  if (!audit?.length) {
    return <p className="co-muted">No related audit events.</p>;
  }
  return (
    <ul className="co-audit">
      {audit.map((log) => (
        <li key={log.id}>
          <strong>{(log.action || "").replace(/_/g, " ")}</strong>
          <span className="co-muted">
            {log.user_email || "system"}
            {log.created_at ? ` · ${new Date(log.created_at).toLocaleString()}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
