import { commissionTableLabel } from "./PlanHeaderForm";

export function formatPlanMonth(plan) {
  const start = plan?.effective_start_date;
  if (!start) return "—";
  const [year, month] = start.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

export function formatEffectiveRange(from, to) {
  if (!from && !to) return "—";
  if (!from) return `→ ${to || "open"}`;
  return `${from} → ${to || "open"}`;
}

export function planRateCount(plan) {
  if (typeof plan?.rates_count === "number") return plan.rates_count;
  return (
    (plan.sc_rate_tables?.length || 0) +
    (plan.sc_flat_rate_tables?.length || 0) +
    (plan.sc_lookup_tables?.length || 0)
  );
}

export function planRuleCount(plan) {
  if (typeof plan?.rules_count === "number") return plan.rules_count;
  return plan.commission_rules?.length || 0;
}

export function planStatusClass(status) {
  const s = String(status || "").toLowerCase();
  if (s === "active" || s === "published") return "cp-plan-status--active";
  if (s === "draft") return "cp-plan-status--draft";
  return "cp-plan-status--inactive";
}

export function displayVersionLabel(plan) {
  const cv = plan?.current_version;
  if (!cv) return "No version";
  return `v${cv.version_number}`;
}

export function calculationMethodLabel(plan) {
  return commissionTableLabel(plan?.commission_table_type || plan?.current_version?.commission_table_type);
}

export function normalizePlansResponse(data) {
  if (Array.isArray(data)) return { results: data, count: data.length };
  if (data?.results) return { results: data.results, count: data.count ?? data.results.length };
  return { results: [], count: 0 };
}

export function formatEffectivePeriodShort(from, to) {
  const fmt = (iso) => {
    if (!iso) return null;
    const [y, m] = String(iso).split("-");
    if (!y || !m) return iso;
    const d = new Date(Number(y), Number(m) - 1, 1);
    return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
  };
  const a = fmt(from);
  const b = fmt(to);
  if (!a && !b) return "—";
  if (!b) return `${a} → open`;
  return `${a} – ${b}`;
}

export function planTypeLabel(plan) {
  if (plan?.plan_type_label) return plan.plan_type_label;
  const map = {
    sales_commission: "Sales Commission",
    bonus_plan: "Bonus Plan",
    manager_override: "Manager Override",
    channel_incentive: "Channel Incentive",
    spiff: "SPIFF",
  };
  if (plan?.plan_type && map[plan.plan_type]) return map[plan.plan_type];
  const basis = plan?.plan_basis || plan?.business_summary?.plan_basis;
  if (basis && basis !== "—") return `${basis} Commission`;
  return calculationMethodLabel(plan) || "Sales Commission";
}

export function formatCoverageList(values, empty = "—") {
  if (!values?.length) return empty;
  if (values.length <= 2) return values.join(", ");
  return `${values.slice(0, 2).join(", ")} +${values.length - 2}`;
}

export function formatMoney(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function healthClass(level) {
  if (level === "healthy") return "cp-health--healthy";
  if (level === "critical") return "cp-health--critical";
  return "cp-health--warning";
}

export const AI_PLAN_EXAMPLES = [
  "Sales reps receive 5% until 100K then 7%.",
  "Managers receive 2% override on team closed-won deals.",
  "Quarterly bonus of $2,000 after 120% quota attainment.",
];
