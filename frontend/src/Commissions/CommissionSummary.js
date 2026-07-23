import { formatMoney } from "../utils/currency";

export function CommissionSummary({ kpis, currency }) {
  const cards = [
    {
      key: "liability",
      label: "Commission Liability",
      value: formatMoney(kpis?.commission_liability, currency, { compact: true }),
      tone: "navy",
    },
    {
      key: "calculated",
      label: "Calculated",
      value: formatMoney(kpis?.calculated, currency, { compact: true }),
      hint: `${kpis?.calculated_count ?? 0} records`,
    },
    {
      key: "pending",
      label: "Pending Approval",
      value: formatMoney(kpis?.pending_approval, currency, { compact: true }),
      hint: `${kpis?.pending_approval_count ?? 0} records`,
      tone: "amber",
    },
    {
      key: "approved",
      label: "Approved",
      value: formatMoney(kpis?.approved, currency, { compact: true }),
      hint: `${kpis?.approved_count ?? 0} records`,
      tone: "teal",
    },
    {
      key: "paid",
      label: "Paid",
      value: formatMoney(kpis?.paid, currency, { compact: true }),
      hint: `${kpis?.paid_count ?? 0} records`,
      tone: "teal",
    },
    {
      key: "exceptions",
      label: "Exceptions",
      value: kpis?.exceptions ?? 0,
      tone: "danger",
    },
    {
      key: "adjustments",
      label: "Adjustments",
      value: formatMoney(kpis?.adjustments, currency, { compact: true }),
      hint: `${kpis?.adjustments_count ?? 0} entries`,
      tone: "amber",
    },
  ];

  return (
    <section className="co-kpis" aria-label="Executive summary">
      {cards.map((c) => (
        <article key={c.key} className={`co-kpi${c.tone ? ` co-kpi--${c.tone}` : ""}`}>
          <span className="co-kpi__label">{c.label}</span>
          <span className="co-kpi__value">{c.value}</span>
          {c.hint ? <span className="co-kpi__hint">{c.hint}</span> : null}
        </article>
      ))}
    </section>
  );
}

export function CommissionProcessStatus({ pipeline }) {
  const steps = [
    { key: "calculated", label: "Calculated", count: pipeline?.calculated ?? 0 },
    { key: "under_review", label: "Under Review", count: pipeline?.under_review ?? 0 },
    { key: "approved", label: "Approved", count: pipeline?.approved ?? 0 },
    { key: "payment_ready", label: "Payment Ready", count: pipeline?.payment_ready ?? 0 },
    { key: "paid", label: "Paid", count: pipeline?.paid ?? 0 },
  ];

  return (
    <section className="co-pipeline panel" aria-label="Commission process status">
      <h2 className="co-section-title">Commission process status</h2>
      <div className="co-pipeline__steps">
        {steps.map((step, idx) => (
          <div key={step.key} className="co-pipeline__step">
            <div className="co-pipeline__card">
              <span className="co-pipeline__label">{step.label}</span>
              <strong className="co-pipeline__count">{step.count}</strong>
            </div>
            {idx < steps.length - 1 ? <span className="co-pipeline__arrow" aria-hidden>↓</span> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
