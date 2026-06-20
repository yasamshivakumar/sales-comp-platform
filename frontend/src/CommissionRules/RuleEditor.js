import DatePickerField from "../Components/DatePickerField";

function emptyCondition(sequence) {
  return {
    field: "product_name",
    operator: "eq",
    value: "",
    sequence,
    is_active: true,
  };
}

function emptyResult(sequence) {
  return {
    result_name: `Result ${sequence}`,
    hold_period: "none",
    result_classification: "commission",
    quota_enabled: false,
    quota_period: "",
    result_rate_type: "override_tier_pct",
    rate_value: "",
    minimum_value: null,
    maximum_value: null,
    earning_group: "base",
    value_unit_type: "percent",
    reason_code: "",
    sequence,
    is_active: true,
  };
}

function resultDefaultsForType(resultType, sequence) {
  if (resultType === "add_bonus") {
    return {
      result_name: `Bonus ${sequence}`,
      value_unit_type: "currency",
      earning_group: "bonus",
      result_classification: "bonus",
    };
  }
  if (resultType === "override_tier_pct" || resultType === "percentage") {
    return {
      result_name: `Rate override ${sequence}`,
      value_unit_type: "percent",
      earning_group: "base",
      result_classification: "commission",
    };
  }
  return {
    result_name: `Result ${sequence}`,
    value_unit_type: "currency",
    earning_group: "base",
    result_classification: "commission",
  };
}

function RuleEditor({ draft, setDraft, choices, plans, currency = "INR" }) {
  const update = (patch) => setDraft({ ...draft, ...patch });
  const amountCurrencyLabel = currency || "order currency";

  const updateCondition = (index, patch) => {
    const conditions = [...(draft.conditions || [])];
    conditions[index] = { ...conditions[index], ...patch };
    update({ conditions });
  };

  const updateResult = (index, patch) => {
    const results = [...(draft.results || [])];
    results[index] = { ...results[index], ...patch };
    update({ results });
  };

  const resultValueLabel = (row) => {
    if (row.result_rate_type === "override_tier_pct" || row.result_rate_type === "percentage") {
      return "Override tier rate (%) *";
    }
    if (row.result_rate_type === "add_bonus") return `Bonus amount (${amountCurrencyLabel}) *`;
    if (row.result_rate_type === "flat_amount" || row.result_rate_type === "override") {
      return `Amount (${amountCurrencyLabel}) *`;
    }
    if (row.result_rate_type === "multiplier") return "Multiplier *";
    return "Value *";
  };

  const primaryRateTypes = (choices?.rate_types || []).filter((opt) =>
    ["override_tier_pct", "add_bonus"].includes(opt.value)
  );
  const advancedRateTypes = (choices?.rate_types || []).filter(
    (opt) => !["override_tier_pct", "add_bonus"].includes(opt.value)
  );
  const resultRateType = (row) =>
    row.result_rate_type === "percentage" ? "override_tier_pct" : row.result_rate_type;

  return (
    <>
      <section className="cr-section">
        <h3 className="cr-section__title">Rule details</h3>
        <p className="cr-hint">
          Required: <strong>Name</strong> and <strong>Compensation plan</strong>. Everything else
          has defaults — add conditions only when the rule should not apply to every order.
        </p>
        <div className="cr-grid">
          <div className="cr-field">
            <label htmlFor="rule-name">Name *</label>
            <input
              id="rule-name"
              value={draft.name}
              onChange={(e) => update({ name: e.target.value })}
              placeholder="e.g. Tech product bonus"
            />
          </div>
          <div className="cr-field">
            <label htmlFor="rule-plan">Compensation plan *</label>
            <select
              id="rule-plan"
              value={draft.compensation_plan || ""}
              onChange={(e) => update({ compensation_plan: e.target.value })}
            >
              <option value="">— Select plan —</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.plan_name}
                </option>
              ))}
            </select>
          </div>
          <div className="cr-field">
            <label htmlFor="rule-sequence">Run order</label>
            <input
              id="rule-sequence"
              type="number"
              min="1"
              value={draft.sequence}
              onChange={(e) => update({ sequence: Number(e.target.value) || 1 })}
            />
          </div>
        </div>
        <div className="cr-version-bar">
          <label>
            <input
              type="checkbox"
              checked={Boolean(draft.is_active)}
              onChange={(e) => update({ is_active: e.target.checked })}
            />{" "}
            Active
          </label>
          <label>
            <input
              type="checkbox"
              checked={Boolean(draft.stop_on_match)}
              onChange={(e) => update({ stop_on_match: e.target.checked })}
            />{" "}
            Stop after this rule matches
          </label>
        </div>
        <div className="cr-grid">
          <div className="cr-field">
            <DatePickerField
              label="Valid from (optional)"
              value={draft.effective_start_date || ""}
              onChange={(value) => update({ effective_start_date: value || null })}
              maxDate={draft.effective_end_date || undefined}
            />
          </div>
          <div className="cr-field">
            <DatePickerField
              label="Valid to (optional)"
              value={draft.effective_end_date || ""}
              onChange={(value) => update({ effective_end_date: value || null })}
              minDate={draft.effective_start_date || undefined}
            />
          </div>
        </div>
      </section>

      <section className="cr-section">
        <h3 className="cr-section__title">Conditions (optional)</h3>
        <p className="cr-hint">
          Leave empty to apply to all orders on the plan. <strong>Product</strong> = CSV{" "}
          <code>product_name</code>; <strong>Service</strong> = <code>service_name</code>.
        </p>
        <div className="cr-table-wrap">
          <table className="cr-table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Operator</th>
                <th>Value</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(draft.conditions || []).length === 0 ? (
                <tr>
                  <td colSpan={4} className="cr-empty">
                    No conditions — applies to all orders on this plan.
                  </td>
                </tr>
              ) : (
                draft.conditions.map((row, index) => (
                  <tr key={index}>
                    <td>
                      <select
                        value={row.field}
                        onChange={(e) => updateCondition(index, { field: e.target.value })}
                      >
                        {(choices?.condition_fields || []).map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={row.operator}
                        onChange={(e) => updateCondition(index, { operator: e.target.value })}
                      >
                        {(choices?.operators || []).map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      {row.field === "currency" ? (
                        <select
                          value={row.value || ""}
                          onChange={(e) => updateCondition(index, { value: e.target.value })}
                        >
                          <option value="">Select currency</option>
                          {(choices?.currencies || []).map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          value={row.value || ""}
                          onChange={(e) => updateCondition(index, { value: e.target.value })}
                          placeholder="Value or comma list"
                        />
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ padding: "4px 8px", fontSize: 12 }}
                        onClick={() =>
                          update({
                            conditions: draft.conditions.filter((_, i) => i !== index),
                          })
                        }
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          className="btn-secondary"
          style={{ marginTop: 8 }}
          onClick={() =>
            update({
              conditions: [
                ...(draft.conditions || []),
                emptyCondition((draft.conditions?.length || 0) + 1),
              ],
            })
          }
        >
          + Add condition
        </button>
      </section>

      <section className="cr-section">
        <h3 className="cr-section__title">Result *</h3>
        <p className="cr-hint">
          <strong>Override tier %</strong> replaces the plan rate table with your percentage when
          conditions match. <strong>Add bonus</strong> keeps the tier rate and adds a flat amount
          on top.
        </p>
        {(draft.results || []).map((row, index) => (
          <div
            key={index}
            className="cr-section"
            style={{ borderTop: index > 0 ? "1px solid #334155" : undefined, paddingTop: index > 0 ? 12 : 0 }}
          >
            <div className="cr-grid">
              <div className="cr-field">
                <label>Result type *</label>
                <select
                  value={resultRateType(row)}
                  onChange={(e) =>
                    updateResult(index, {
                      ...resultDefaultsForType(e.target.value, index + 1),
                      result_rate_type: e.target.value,
                    })
                  }
                >
                  {primaryRateTypes.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                  {advancedRateTypes.length > 0 && (
                    <optgroup label="Advanced">
                      {advancedRateTypes.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </div>
              <div className="cr-field">
                <label>{resultValueLabel(row)}</label>
                <input
                  type="number"
                  step="0.0001"
                  value={row.rate_value ?? ""}
                  onChange={(e) => updateResult(index, { rate_value: e.target.value })}
                />
              </div>
            </div>
            {(draft.results?.length || 0) > 1 && (
              <button
                type="button"
                className="btn-secondary"
                style={{ marginTop: 8 }}
                onClick={() =>
                  update({ results: draft.results.filter((_, i) => i !== index) })
                }
              >
                Remove result
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          className="btn-secondary"
          onClick={() =>
            update({
              results: [...(draft.results || []), emptyResult((draft.results?.length || 0) + 1)],
            })
          }
        >
          + Add result
        </button>
      </section>
    </>
  );
}

export default RuleEditor;
