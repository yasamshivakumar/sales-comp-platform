function TierList({ selectedPlan }) {
  const isFlat = selectedPlan?.commission_table_type === "FLAT";
  const rateRows = selectedPlan?.sc_rate_tables || [];
  const flatRows = selectedPlan?.sc_flat_rate_tables || [];
  const hasRows = isFlat ? flatRows.length > 0 : rateRows.length > 0;

  return (
    <div className="panel">
      <h3 className="panel__title">Current rates</h3>

      {!hasRows ? (
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          No commission rates yet. Add at least one rate — orders will not earn commission until a
          rate exists on this plan.
        </p>
      ) : isFlat ? (
        flatRows.map((row, index) => (
          <div key={row.id ?? index} className="tier-list-item">
            <strong>Flat rate</strong>
            <p>Commission: {row.flat_rate}%</p>
            <p>Active: {row.is_active !== false ? "Yes" : "No"}</p>
          </div>
        ))
      ) : (
        rateRows.map((row, index) => (
          <div key={row.id ?? index} className="tier-list-item">
            <strong>{row.tier_name || `Tier ${row.sequence || index + 1}`}</strong>
            <p>
              Sales range: {row.from_amount} – {row.to_amount ?? "No limit"}
            </p>
            <p>Commission: {row.commission_rate}%</p>
            {parseFloat(row.bonus_amount) > 0 && <p>Bonus: {row.bonus_amount}</p>}
          </div>
        ))
      )}
    </div>
  );
}

export default TierList;
