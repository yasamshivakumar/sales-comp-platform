import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import { formatMoney, normalizeCurrency } from "../utils/currency";
import { businessGroupLabel, currencyForBusinessGroup } from "../utils/businessGroups";
import RuleEditor from "./RuleEditor";
import "./commissionRules.css";

const EMPTY_RULE = {
  name: "",
  rule_type: "commission_rate",
  multiplier: "1",
  effective_start_date: "",
  effective_end_date: "",
  sequence: 1,
  is_active: true,
  stop_on_match: false,
  apply_to_all_plan_participants: false,
  compensation_plan: "",
  assigned_employee_ids: [],
  conditions: [],
  results: [
    {
      result_name: "Result 1",
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
      sequence: 1,
      is_active: true,
    },
  ],
};

function normalizeResult(row, index) {
  const rateType = row.result_rate_type || "override_tier_pct";
  let normalizedRateType = rateType === "percentage" ? "override_tier_pct" : rateType;
  let classification = row.result_classification || "commission";
  let earningGroup = row.earning_group || "base";
  let valueUnit = row.value_unit_type || "currency";

  if (rateType === "add_bonus") {
    classification = "bonus";
    earningGroup = "bonus";
    valueUnit = "currency";
  } else if (rateType === "override_tier_pct" || rateType === "percentage") {
    classification = "commission";
    earningGroup = "base";
    valueUnit = "percent";
  } else if (rateType === "flat_amount" || rateType === "override") {
    classification = "commission";
    earningGroup = "base";
    valueUnit = "currency";
  }

  const { id, rule, ...rest } = row;
  return {
    ...rest,
    result_name: rest.result_name?.trim() || `Result ${index + 1}`,
    hold_period: rest.hold_period || "none",
    result_classification: classification,
    earning_group: earningGroup,
    value_unit_type: valueUnit,
    result_rate_type: normalizedRateType,
    quota_enabled: false,
    quota_period: "",
    reason_code: "",
    sequence: rest.sequence || index + 1,
    is_active: true,
    rate_value: rest.rate_value === "" || rest.rate_value == null ? null : rest.rate_value,
    minimum_value: null,
    maximum_value: null,
  };
}

function conditionCurrency(conditions = []) {
  const currencyCondition = conditions.find(
    (row) => row.field === "currency" && row.value
  );
  if (!currencyCondition) return "";
  const firstCurrency = String(currencyCondition.value).split(",")[0].trim();
  return normalizeCurrency(firstCurrency, "");
}

function planCurrency(plan, draft) {
  return (
    conditionCurrency(draft?.conditions) ||
    plan?.currency ||
    currencyForBusinessGroup(plan?.business_group || "", "")
  );
}

function resultSummary(result, currency, fallbackResult) {
  if (!result || result.rate_value == null) return "";
  const value = result.rate_value;
  const type = fallbackResult?.result_rate_type || result.result_rate_type;
  const money = currency
    ? formatMoney(value, currency)
    : `${Number(value).toFixed(2)} in order currency`;
  if (type === "add_bonus") {
    return `Bonus ${money}`;
  }
  if (type === "flat_amount" || type === "override") {
    return `Amount ${money}`;
  }
  if (type === "override_tier_pct" || type === "percentage") {
    return `Rate ${Number(value).toFixed(2)}%`;
  }
  if (type === "multiplier") {
    return `Multiplier ${value}x`;
  }
  return `Value ${value}`;
}

function CommissionRules() {
  const [searchParams] = useSearchParams();
  const [rules, setRules] = useState([]);
  const [plans, setPlans] = useState([]);
  const [people, setPeople] = useState([]);
  const [choices, setChoices] = useState(null);
  const [invalidAssignments, setInvalidAssignments] = useState([]);
  const [planFilter, setPlanFilter] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const { success, error } = useToast();
  const selectedPlan = plans.find((plan) => String(plan.id) === String(draft?.compensation_plan));
  const selectedCurrency = planCurrency(selectedPlan, draft);

  const fetchRules = useCallback(() => {
    setLoading(true);
    const params = planFilter ? `?plan_id=${planFilter}` : "";
    api
      .get(`commission-rules/${params}`)
      .then((res) => setRules(res.data))
      .catch(() => error("Failed to load commission rules"))
      .finally(() => setLoading(false));
  }, [planFilter, error]);

  // Lightweight list for Employee ID condition dropdown (picker loads its own pages).
  const fetchConditionPeople = useCallback((planId) => {
    if (!planId) {
      setPeople([]);
      return;
    }
    setPeople([]);
    api
      .get(
        `commission-rules/eligible-employees/?plan_id=${planId}&page=1&page_size=500`
      )
      .then((res) => {
        const data = res.data;
        const rows = Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
            ? data
            : [];
        setPeople(rows);
      })
      .catch(() => setPeople([]));
  }, []);

  useEffect(() => {
    const planFromUrl = searchParams.get("plan");
    if (planFromUrl) setPlanFilter(planFromUrl);
  }, [searchParams]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  useEffect(() => {
    fetchConditionPeople(draft?.compensation_plan);
  }, [draft?.compensation_plan, fetchConditionPeople]);

  const fetchInvalidAssignments = useCallback(() => {
    api
      .get("commission-rules/invalid-assignments/")
      .then((res) => setInvalidAssignments(res.data?.assignments || []))
      .catch(() => setInvalidAssignments([]));
  }, []);

  useEffect(() => {
    api
      .get("compensation-plans/")
      .then((res) => setPlans(res.data))
      .catch(() => error("Failed to load compensation plans"));
    api
      .get("commission-rules/choices/")
      .then((res) => setChoices(res.data))
      .catch(() => error("Failed to load rule choices"));
    fetchInvalidAssignments();
  }, [error, fetchInvalidAssignments]);

  const selectRule = async (id) => {
    if (!id) {
      setSelectedId(null);
      setDraft(null);
      return;
    }
    try {
      const res = await api.get(`commission-rules/${id}/`);
      setSelectedId(id);
      setDraft({
        ...res.data,
        compensation_plan: res.data.compensation_plan || "",
        multiplier: String(res.data.multiplier ?? "1"),
        assigned_employee_ids: (res.data.assigned_employees || []).map((row) =>
          Number(row.id)
        ),
        conditions: res.data.conditions || [],
        results: res.data.results?.length
          ? res.data.results
          : EMPTY_RULE.results,
      });
    } catch {
      error("Failed to load rule");
    }
  };

  const startCreate = () => {
    setSelectedId(null);
    setDraft({
      ...EMPTY_RULE,
      compensation_plan: planFilter || "",
      name: "New Rule",
    });
  };

  const saveRule = async () => {
    if (!draft?.name?.trim()) {
      error("Rule name is required");
      return;
    }
    if (!draft.compensation_plan) {
      error("Compensation plan is required");
      return;
    }
    if (!draft.apply_to_all_plan_participants && !(draft.assigned_employee_ids || []).length) {
      error("Select at least one employee, or enable Apply to all plan participants");
      return;
    }
    const hasRateValue = (draft.results || []).some(
      (row) => row.rate_value !== "" && row.rate_value != null
    );
    if (!hasRateValue) {
      error("Enter a result value (override tier % or bonus amount)");
      return;
    }
    setSaving(true);
    const payload = {
      name: draft.name.trim(),
      rule_type: draft.rule_type || "commission_rate",
      multiplier: draft.multiplier || "1",
      compensation_plan: draft.compensation_plan,
      effective_start_date: draft.effective_start_date || null,
      effective_end_date: draft.effective_end_date || null,
      active_start_date: null,
      active_end_date: null,
      sequence: draft.sequence || 1,
      is_active: draft.is_active !== false,
      stop_on_match: Boolean(draft.stop_on_match),
      apply_to_all_plan_participants: Boolean(draft.apply_to_all_plan_participants),
      description: draft.description || "",
      tags: draft.tags || [],
      assigned_employee_ids: draft.apply_to_all_plan_participants
        ? []
        : (draft.assigned_employee_ids || []).map((id) => Number(id)),
      conditions: (draft.conditions || []).map((row, index) => {
        const { id, rule, ...rest } = row;
        return {
          ...rest,
          sequence: rest.sequence || index + 1,
          is_active: true,
        };
      }),
      results: (draft.results || []).map((row, index) => normalizeResult(row, index)),
    };
    try {
      const savedMessage = (rule) => {
        const summary = resultSummary(
          rule?.results?.[0],
          selectedCurrency,
          payload.results?.[0]
        );
        return summary
          ? `Rule saved (${summary}). Click Recalculate on Commissions to update existing orders.`
          : "Rule saved. Click Recalculate on Commissions to update existing orders.";
      };
      if (selectedId) {
        const res = await api.patch(`commission-rules/${selectedId}/`, payload);
        success(savedMessage(res.data));
        fetchRules();
        fetchInvalidAssignments();
        selectRule(selectedId);
      } else {
        const res = await api.post("commission-rules/", payload);
        success(savedMessage(res.data).replace("Rule saved", "Rule created"));
        fetchRules();
        fetchInvalidAssignments();
        selectRule(res.data.id);
      }
    } catch (err) {
      const data = err.response?.data;
      const msg =
        data?.employee_ids ||
        data?.detail ||
        data?.error ||
        (typeof data === "string" ? data : null) ||
        "Failed to save rule";
      error(Array.isArray(msg) ? msg.join(" ") : String(msg));
    } finally {
      setSaving(false);
    }
  };

  const deleteRule = async () => {
    if (!selectedId || !window.confirm("Delete this commission rule?")) return;
    try {
      await api.delete(`commission-rules/${selectedId}/`);
      success("Rule deleted");
      setSelectedId(null);
      setDraft(null);
      fetchRules();
    } catch {
      error("Failed to delete rule");
    }
  };

  return (
    <div className="cr-root">
      <PageHeader badge="Configuration" title="Commission Rules" />

      {invalidAssignments.length > 0 && (
        <div className="panel cr-invalid-banner" role="status">
          <strong>{invalidAssignments.length} invalid assignment(s)</strong>
          <p>
            Some employees are linked to rules whose Compensation Plan no longer matches.
            Those assignments are ignored in calculation until corrected. Open each rule and
            re-select only employees on that plan.
          </p>
          <ul>
            {invalidAssignments.slice(0, 8).map((row) => (
              <li key={row.assignment_id}>
                {row.employee_name || row.employee_code} → {row.rule_name} ({row.reason})
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="cr-toolbar panel" style={{ padding: "12px 16px" }}>
        <div className="cr-plan-filter">
          <label htmlFor="cr-plan-filter">Compensation plan</label>
          <select
            id="cr-plan-filter"
            value={planFilter}
            onChange={(e) => {
              setPlanFilter(e.target.value);
              setSelectedId(null);
              setDraft(null);
            }}
          >
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.plan_name} ({plan.role || "—"}
                {plan.business_group
                  ? ` · ${businessGroupLabel(plan.business_group)} ${currencyForBusinessGroup(plan.business_group, "")}`
                  : ""})
              </option>
            ))}
          </select>
        </div>
        <div className="cr-toolbar__actions">
          <button type="button" className="btn-primary" onClick={startCreate}>
            + Create Rule
          </button>
        </div>
      </div>

      <div className="cr-layout">
        <div className="panel cr-list">
          <div className="cr-list__head">Rules ({rules.length})</div>
          {loading ? (
            <p className="cr-empty">Loading…</p>
          ) : rules.length === 0 ? (
            <p className="cr-empty">No rules yet. Create one to define conditions and results.</p>
          ) : (
            <ul className="cr-list__items">
              {rules.map((rule) => (
                <li key={rule.id}>
                  <button
                    type="button"
                    className={`cr-list__item${
                      selectedId === rule.id ? " cr-list__item--active" : ""
                    }`}
                    onClick={() => selectRule(rule.id)}
                  >
                    <span className="cr-list__item-name">{rule.name}</span>
                    <span className="cr-list__item-meta">
                      {rule.rule_type} · {rule.plan_name || "No plan"} · seq {rule.sequence}
                      {" · "}
                      {rule.apply_to_all_plan_participants
                        ? "All plan participants"
                        : `${rule.assignee_count ?? rule.assigned_employees?.length ?? 0} employees`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel cr-editor">
          {!draft ? (
            <p className="cr-empty">
              Select a rule or click <strong>Create Rule</strong> to configure general details,
              conditions, and results.
            </p>
          ) : (
            <>
              <RuleEditor
                draft={draft}
                setDraft={setDraft}
                choices={choices}
                plans={plans}
                people={people}
                currency={selectedCurrency}
              />
              <div className="cr-actions">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={saveRule}
                  disabled={saving}
                >
                  {saving ? "Saving…" : selectedId ? "Save changes" : "Create rule"}
                </button>
                {selectedId && (
                  <button type="button" className="btn-secondary" onClick={deleteRule}>
                    Delete
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default CommissionRules;
