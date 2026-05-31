function TierList({ tiers }) {
  return (
    <div className="panel">
      <h3 className="panel__title">Plan tiers</h3>

      {tiers.length === 0 ? (
        <p style={{ color: "var(--text-muted)", margin: 0 }}>No tiers defined yet.</p>
      ) : (
        tiers.map((tier) => (
          <div key={tier.id} className="tier-list-item">
            <strong>{tier.tier_name}</strong>
            <p>
              Sales range: {tier.min_sales} – {tier.max_sales}
            </p>
            <p>Commission: {tier.commission_percent}%</p>
            <p>Bonus: {tier.bonus_amount}</p>
          </div>
        ))
      )}
    </div>
  );
}

export default TierList;
