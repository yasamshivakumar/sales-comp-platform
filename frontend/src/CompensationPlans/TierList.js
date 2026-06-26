import { formatMoney } from "../utils/currency";
import { currencyForBusinessGroup } from "../utils/businessGroups";

function TierList({ selectedPlan, onEditTier }) {
  const isFlat = selectedPlan?.commission_table_type === "FLAT";
  const rateRows = selectedPlan?.sc_rate_tables || [];
  const flatRows = selectedPlan?.sc_flat_rate_tables || [];
  const hasRows = isFlat ? flatRows.length > 0 : rateRows.length > 0;
  const currency = selectedPlan?.currency || currencyForBusinessGroup(selectedPlan?.business_group || "", "");
  const money = (value) => (currency ? formatMoney(value, currency) : value);

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
            <div className="tier-list-item__head">
              <strong>Flat rate</strong>
              <button type="button" className="btn-secondary" onClick={() => onEditTier?.(row, index)}>
                Edit
              </button>
            </div>
            <p>Commission: {row.flat_rate}%</p>
            <p>Active: {row.is_active !== false ? "Yes" : "No"}</p>
          </div>
        ))
      ) : (
        rateRows.map((row, index) => (
          <div key={row.id ?? index} className="tier-list-item">
            <div className="tier-list-item__head">
              <strong>{row.tier_name || `Tier ${row.sequence || index + 1}`}</strong>
              <button type="button" className="btn-secondary" onClick={() => onEditTier?.(row, index)}>
                Edit
              </button>
            </div>
            <p>
              Sales range: {money(row.from_amount)} – {row.to_amount != null ? money(row.to_amount) : "No limit"}
            </p>
            <p>Commission: {row.commission_rate}%</p>
            {parseFloat(row.bonus_amount) > 0 && <p>Bonus: {money(row.bonus_amount)}</p>}
          </div>
        ))
      )}
    </div>
  );
}

export default TierList;
