import { Link, useOutletContext } from "react-router-dom";

function summarizeConditions(rule) {
  const conditions = rule.conditions || [];
  if (!conditions.length) return { all: "Any", products: "—", customers: "—", territories: "—", roles: "—" };

  const byField = (field) =>
    conditions
      .filter((c) => c.field === field)
      .map((c) => `${c.operator || ""} ${c.value || ""}`.trim())
      .filter(Boolean)
      .join(", ") || "—";

  return {
    all: conditions
      .map((c) => `${c.field} ${c.operator} ${c.value}`)
      .slice(0, 3)
      .join("; ") || "Any",
    products: byField("product_name"),
    customers: byField("customer_segment"),
    territories: byField("territory_code") !== "—" ? byField("territory_code") : byField("region"),
    roles: byField("role") !== "—" ? byField("role") : byField("position_name"),
  };
}

function RulesTab() {
  const { plan } = useOutletContext();
  const rules = plan.commission_rules || [];

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <div className="cp-tab-panel__head">
          <div>
            <h2 className="panel__title">Rules</h2>
            <p className="cp-tab-lead">
              Priority, conditions, and scope for this plan version. Edit full logic in
              Commission Rules.
            </p>
          </div>
          <Link className="btn-primary" to={`/commission-rules?plan=${plan.id}`}>
            Manage commission rules
          </Link>
        </div>

        {rules.length === 0 ? (
          <div className="cp-empty-inline">
            <p>No rules configured</p>
            <p className="cp-tab-lead">Create rules for multipliers, bonuses, and eligibility filters.</p>
            <Link className="btn-primary" to={`/commission-rules?plan=${plan.id}`}>
              Create rule
            </Link>
          </div>
        ) : (
          <div className="enterprise-table-wrap">
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Name</th>
                  <th>Conditions</th>
                  <th>Products</th>
                  <th>Customers</th>
                  <th>Territories</th>
                  <th>Roles</th>
                  <th>Status</th>
                  <th>Effective</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => {
                  const c = summarizeConditions(rule);
                  return (
                    <tr key={rule.id}>
                      <td>{rule.sequence ?? "—"}</td>
                      <td>
                        <strong>{rule.name}</strong>
                        <div className="muted-mini">{rule.rule_type}</div>
                      </td>
                      <td>{c.all}</td>
                      <td>{c.products}</td>
                      <td>{c.customers}</td>
                      <td>{c.territories}</td>
                      <td>{c.roles}</td>
                      <td>{rule.is_active ? "Active" : "Inactive"}</td>
                      <td>
                        {(rule.effective_start_date || "—") +
                          " → " +
                          (rule.effective_end_date || "open")}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default RulesTab;
