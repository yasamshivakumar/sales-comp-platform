import { formatMoney } from "../utils/currency";
import { currencyForBusinessGroup } from "../utils/businessGroups";

function dimLabel(value) {
  const text = (value || "").trim();
  return text || "Any";
}

function LookupTierList({ selectedPlan }) {
  const rows = selectedPlan?.sc_lookup_tables || [];
  const currency = selectedPlan?.currency || currencyForBusinessGroup(selectedPlan?.business_group || "", "");
  const money = (value) => (currency ? formatMoney(value, currency) : value);

  return (
    <div className="panel">
      <h3 className="panel__title">Current lookup tiers</h3>
      {rows.length === 0 ? (
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          No lookup tiers yet. Add rows that match product, service, distribution, and sales
          band — orders only earn commission when a row matches.
        </p>
      ) : (
        rows.map((row, index) => (
          <div key={row.id ?? index} className="tier-list-item">
            <strong>{row.tier_name || `Lookup ${row.sequence || index + 1}`}</strong>
            <p>
              Product: {dimLabel(row.product_name)} · Service: {dimLabel(row.service_name)} ·
              Distribution: {dimLabel(row.distribution)}
            </p>
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

export default LookupTierList;
