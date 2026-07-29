import DatePickerField from "../Components/DatePickerField";
import EmployeeAssigneePicker from "./EmployeeAssigneePicker";

function clientRowKey() {
  return `row-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function emptyCondition(sequence) {
  return {
    _key: clientRowKey(),
    field: "product_name",
    operator: "eq",
    value: "",
    sequence,
    is_active: true,
  };
}

function emptyResult(sequence) {
  return {
    _key: clientRowKey(),
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

function RuleEditor({ draft, setDraft, choices, plans, people = [], currency = "INR" }) {
  const update = (patch) => setDraft({ ...draft, ...patch });
  const amountCurrencyLabel = currency || "order currency";
  const planId = draft.compensation_plan ? Number(draft.compensation_plan) : null;
  const selectedIds = draft.assigned_employee_ids || [];

  const onPlanChange = (nextPlanId) => {
    // Changing plan clears assignees; picker reloads for the new plan only.
    update({
      compensation_plan: nextPlanId || "",
      assigned_employee_ids: [],
      assigned_employees: [],
    });
  };

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
              onChange={(e) => onPlanChange(e.target.value)}
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
        <h3 className="cr-section__title">Employees *</h3>
        <p className="cr-hint">
          Choose who this rule applies to. You can select specific people, or apply it to
          everyone on the Compensation Plan (including people who join the plan later).
        </p>
        <label className="cr-checkbox-row">
          <input
            type="checkbox"
            checked={Boolean(draft.apply_to_all_plan_participants)}
            onChange={(e) =>
              update({
                apply_to_all_plan_participants: e.target.checked,
                assigned_employee_ids: e.target.checked
                  ? []
                  : draft.assigned_employee_ids || [],
              })
            }
          />
          <span>
            <strong>Apply to all plan participants</strong>
            <span className="cr-hint" style={{ display: "block", marginTop: 2 }}>
              Stays in sync when people are added to or removed from this Compensation Plan.
              No need to pick employees individually.
            </span>
          </span>
        </label>
        {draft.apply_to_all_plan_participants ? (
          <div className="cr-assignee-empty">
            This rule will apply to every employee on{" "}
            <strong>
              {plans.find((p) => String(p.id) === String(draft.compensation_plan))
                ?.plan_name || "the selected plan"}
            </strong>
            , including future participants.
          </div>
        ) : (
          <>
            <EmployeeAssigneePicker
              planId={planId}
              selectedIds={selectedIds}
              onChange={(ids) => update({ assigned_employee_ids: ids })}
              initialPeople={draft.assigned_employees || []}
            />
            {planId && selectedIds.length === 0 && (
              <p className="cr-hint cr-hint--warn">
                Select at least one employee before saving, or enable Apply to all plan
                participants.
              </p>
            )}
          </>
        )}
      </section>

      <section className="cr-section">
        <h3 className="cr-section__title">Conditions (optional)</h3>
        <p className="cr-hint">
          Conditions define <strong>when</strong> the rule applies to the selected employees
          (product, region, amount, etc.). Leave empty to apply to all of their orders.
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
                    No conditions — applies to all orders for the assigned employees.
                  </td>
                </tr>
              ) : (
                draft.conditions.map((row, index) => (
                  <tr key={row.id ?? row._key ?? `condition-${index}`}>
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
                      ) : row.field === "employee_id" && people.length > 0 ? (
                        <select
                          value={row.value || ""}
                          onChange={(e) => updateCondition(index, { value: e.target.value })}
                        >
                          <option value="">Select employee…</option>
                          {people
                            .filter((p) => (p.employee_id || "").trim())
                            .map((person) => (
                              <option key={person.id} value={person.employee_id}>
                                {(person.name || person.email || "Employee") +
                                  ` (${person.employee_id})`}
                              </option>
                            ))}
                          {row.value &&
                          !people.some(
                            (p) => String(p.employee_id) === String(row.value)
                          ) ? (
                            <option value={row.value}>{row.value} (current)</option>
                          ) : null}
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
            key={row.id ?? row._key ?? `result-${index}`}
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
