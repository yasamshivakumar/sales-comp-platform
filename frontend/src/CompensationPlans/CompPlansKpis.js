/**
 * Top-line portfolio metrics for Compensation Operations Center
 */
const KPI_DEFS = [
  { key: "total_plans", label: "Total Plans", tone: "" },
  { key: "published_plans", label: "Active Plans", tone: "success" },
  { key: "draft_plans", label: "Draft Plans", tone: "" },
  { key: "employees_covered", label: "Employees Covered", tone: "teal" },
  { key: "plans_blocked", label: "Calculation Blocked", tone: "warning", filterCalc: "blocked" },
  {
    key: "plans_requiring_attention",
    label: "Plans Requiring Action",
    tone: "warning",
    filterHealth: "attention",
  },
  { key: "estimated_monthly_commission", label: "Est. Monthly Commission", tone: "", money: true },
];

function CompPlansKpis({ summary, loading, onFilterHealth, onFilterCalc }) {
  return (
    <section className="cp-ops-kpis" aria-label="Summary metrics">
      <div className="cp-ops-kpis__grid">
        {KPI_DEFS.map((kpi) => {
          const raw = summary?.[kpi.key];
          let display = "—";
          if (!(loading || summary == null)) {
            display = kpi.money
              ? `₹${Number(raw || 0).toLocaleString()}`
              : Number(raw || 0).toLocaleString();
          }
          const clickable = Boolean(kpi.filterCalc || kpi.filterHealth);
          const onClick = () => {
            if (kpi.filterCalc) onFilterCalc?.(kpi.filterCalc);
            else if (kpi.filterHealth) onFilterHealth?.(kpi.filterHealth);
          };
          return (
            <article
              key={kpi.key}
              className={`cp-ops-kpi${kpi.tone ? ` cp-ops-kpi--${kpi.tone}` : ""}${
                clickable ? " cp-ops-kpi--clickable" : ""
              }`}
            >
              <span className="cp-ops-kpi__label">{kpi.label}</span>
              {clickable ? (
                <button type="button" className="cp-ops-kpi__value" onClick={onClick}>
                  {display}
                </button>
              ) : (
                <span className="cp-ops-kpi__value">{display}</span>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default CompPlansKpis;
