import { Link, useOutletContext } from "react-router-dom";

function ruleUpdated(rule) {
  return rule.updated_at ? new Date(rule.updated_at).toLocaleString() : "—";
}

function isBonusRule(rule) {
  const results = rule.results || [];
  return results.some((r) => {
    const text = `${r.result_classification || ""} ${r.result_rate_type || ""}`.toLowerCase();
    return text.includes("bonus") || text.includes("spiff");
  });
}

function isAcceleratorRule(rule) {
  return rule.rule_type === "multiplier" || Number(rule.multiplier) > 1;
}

function ComponentTable({ rows }) {
  if (!rows.length) {
    return (
      <div className="cp-empty-inline">
        <p>Not Configured</p>
        <p className="cp-tab-lead">Nothing derived from the current version yet.</p>
      </div>
    );
  }
  return (
    <div className="enterprise-table-wrap">
      <table className="enterprise-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Last updated</th>
            <th>Owner</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.name}</td>
              <td>{row.type}</td>
              <td>{row.status}</td>
              <td>{row.updated}</td>
              <td>{row.owner}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BonusesTab() {
  const { plan } = useOutletContext();
  const rules = (plan.commission_rules || []).filter(isBonusRule);
  const rates = [
    ...(plan.sc_rate_tables || []),
    ...(plan.sc_flat_rate_tables || []),
    ...(plan.sc_lookup_tables || []),
  ].filter((r) => Number(r.bonus_amount) > 0);

  const rows = rules.map((rule) => ({
    id: rule.id,
    name: rule.name,
    type: rule.rule_type || "bonus",
    status: rule.is_active ? "Active" : "Inactive",
    updated: ruleUpdated(rule),
    owner: "Plan rules",
  }));

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <div className="cp-tab-panel__head">
          <div>
            <h2 className="panel__title">Bonuses</h2>
            <p className="cp-tab-lead">
              Bonus and SPIF outcomes from rules, plus tier bonus amounts.
            </p>
          </div>
          <Link className="btn-primary" to={`/commission-rules?plan=${plan.id}`}>
            Manage in Commission Rules
          </Link>
        </div>
        <ComponentTable rows={rows} />
        {rates.length > 0 ? (
          <div className="cp-rate-bands" style={{ marginTop: 16 }}>
            <h3 className="panel__title">Tier bonuses</h3>
            {rates.map((r) => (
              <div key={r.id} className="cp-rate-band">
                <div className="cp-rate-band__range">{r.tier_name || "Tier"}</div>
                <div className="cp-rate-band__bar" />
                <div className="cp-rate-band__rate">{r.bonus_amount}</div>
                <div className="cp-rate-band__label">Configured · bonus amount</div>
              </div>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}

export function AcceleratorsTab() {
  const { plan } = useOutletContext();
  const rows = (plan.commission_rules || []).filter(isAcceleratorRule).map((rule) => ({
    id: rule.id,
    name: rule.name,
    type: `×${rule.multiplier ?? 1}`,
    status: rule.is_active ? "Active" : "Inactive",
    updated: ruleUpdated(rule),
    owner: "Plan rules",
  }));

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <div className="cp-tab-panel__head">
          <div>
            <h2 className="panel__title">Accelerators</h2>
            <p className="cp-tab-lead">
              Multiplier and credit-style rules that accelerate payout.
            </p>
          </div>
          <Link className="btn-primary" to={`/commission-rules?plan=${plan.id}`}>
            Manage in Commission Rules
          </Link>
        </div>
        <ComponentTable rows={rows} />
      </section>
    </div>
  );
}

export default BonusesTab;
