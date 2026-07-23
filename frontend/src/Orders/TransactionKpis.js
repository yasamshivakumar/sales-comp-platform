const KPI_DEFS = [
  { key: "total_transactions", label: "Total Orders" },
  { key: "pending_review", label: "Pending Review", status: "Booked", tone: "warning" },
  { key: "approved_transactions", label: "Approved Orders", status: "Success", tone: "success" },
  { key: "commission_calculated", label: "Commission Calculated", tone: "teal" },
  { key: "failed_transactions", label: "Failed Orders", tone: "warning" },
  { key: "total_sales_value", label: "Total Sales Value", money: true },
  { key: "commission_generated", label: "Commission Generated", money: true },
];

function TransactionKpis({ summary, loading, onFilterStatus }) {
  return (
    <section className="tx-kpis" aria-label="Summary metrics">
      <div className="tx-kpis__grid">
        {KPI_DEFS.map((kpi) => {
          const raw = summary?.[kpi.key];
          let display = "—";
          if (!(loading || summary == null)) {
            display = kpi.money
              ? `₹${Number(raw || 0).toLocaleString()}`
              : Number(raw || 0).toLocaleString();
          }
          const clickable = Boolean(kpi.status);
          return (
            <article
              key={kpi.key}
              className={`tx-kpi${kpi.tone ? ` tx-kpi--${kpi.tone}` : ""}`}
            >
              <span className="tx-kpi__label">{kpi.label}</span>
              {clickable ? (
                <button
                  type="button"
                  className="tx-kpi__value"
                  onClick={() => onFilterStatus?.(kpi.status)}
                >
                  {display}
                </button>
              ) : (
                <span className="tx-kpi__value">{display}</span>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default TransactionKpis;
