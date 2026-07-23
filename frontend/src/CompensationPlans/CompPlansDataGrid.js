import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import {
  displayVersionLabel,
  formatEffectivePeriodShort,
  formatMoney,
  planStatusClass,
  planTypeLabel,
} from "./compPlanUtils";

const COMPONENT_PILLS = [
  { key: "rate_tables", short: "Rate Tables" },
  { key: "eligibility", short: "Eligibility" },
  { key: "participants", short: "Participants" },
  { key: "rules", short: "Rules" },
  { key: "monthly_quotas", short: "Quotas" },
];

function healthLabel(level) {
  if (level === "healthy") return "Healthy";
  if (level === "critical") return "Critical";
  return "Review Required";
}

function calcBadge(calc) {
  const status = calc?.status || "pending";
  if (status === "ready") return { text: "Ready", cls: "ready" };
  if (status === "blocked") return { text: "Blocked", cls: "blocked" };
  return { text: "Pending", cls: "pending" };
}

function simulateCommission(plan, salesAmount) {
  const sales = Number(salesAmount) || 0;
  const type = String(plan.commission_table_type || "RATE").toUpperCase();
  const marginal =
    type === "MARGINAL" || plan.tier_calculation_method === "marginal";
  const steps = [];
  let total = 0;

  if (type === "FLAT") {
    const row = (plan.sc_flat_rate_tables || [])[0];
    const rate = Number(row?.flat_rate ?? row?.commission_rate ?? 0);
    total = (sales * rate) / 100;
    steps.push({ label: "Flat rate", detail: `₹${sales.toLocaleString()} × ${rate}%`, amount: total });
    return { total, steps };
  }

  const bands = [...(plan.sc_rate_tables || [])].sort(
    (a, b) => Number(a.from_amount || 0) - Number(b.from_amount || 0)
  );
  if (!bands.length) {
    return { total: 0, steps: [{ label: "No rates", detail: "Configure rate tables", amount: 0 }] };
  }

  if (marginal) {
    let prev = 0;
    bands.forEach((band, idx) => {
      const from = Number(band.from_amount ?? 0);
      const to = band.to_amount == null || band.to_amount === "" ? Infinity : Number(band.to_amount);
      const rate = Number(band.commission_rate ?? 0);
      const sliceStart = Math.max(prev, from);
      const sliceEnd = Math.min(sales, to);
      if (sliceEnd > sliceStart) {
        const amt = ((sliceEnd - sliceStart) * rate) / 100;
        total += amt;
        steps.push({
          label: band.tier_name || `Tier ${idx + 1}`,
          detail: `₹${(sliceEnd - sliceStart).toLocaleString()} × ${rate}%`,
          amount: amt,
        });
      }
      prev = to === Infinity ? sales : to;
    });
  } else {
    const band =
      bands.find((b) => {
        const from = Number(b.from_amount ?? 0);
        const to = b.to_amount == null || b.to_amount === "" ? Infinity : Number(b.to_amount);
        return sales >= from && sales <= to;
      }) || bands[bands.length - 1];
    const rate = Number(band.commission_rate ?? 0);
    total = (sales * rate) / 100;
    steps.push({
      label: band.tier_name || "Landing tier",
      detail: `₹${sales.toLocaleString()} × ${rate}%`,
      amount: total,
    });
  }
  return { total, steps };
}

export function SimulateCommissionModal({ plan, onClose }) {
  const [amount, setAmount] = useState("500000");
  const [period, setPeriod] = useState(() => new Date().toISOString().slice(0, 7));
  const [employee, setEmployee] = useState("Sample Employee");
  const [detail, setDetail] = useState(plan);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get(`compensation-plans/${plan.id}/`);
        if (!cancelled) setDetail(res.data);
      } catch {
        if (!cancelled) setDetail(plan);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [plan]);

  const result = useMemo(() => simulateCommission(detail || plan, amount), [detail, plan, amount]);

  return (
    <div className="cp-sim-overlay" role="dialog" aria-modal="true" aria-labelledby="cp-sim-title">
      <div className="cp-sim-modal cp-sim-modal--wide">
        <div className="cp-sim-modal__head">
          <h3 id="cp-sim-title">Simulate Commission</h3>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="cp-ops-muted">
          {plan.plan_name} — test payout before publishing
        </p>
        <div className="cp-sim-grid">
          <label>
            Employee
            <input value={employee} onChange={(e) => setEmployee(e.target.value)} />
          </label>
          <label>
            Sales amount
            <input
              type="number"
              min="0"
              step="1000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={loading}
            />
          </label>
          <label>
            Period
            <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} />
          </label>
        </div>
        <div className="cp-sim-result">
          <span className="cp-card__label">Expected commission</span>
          <strong>{loading ? "…" : `₹${Math.round(result.total).toLocaleString()}`}</strong>
        </div>
        <h4 className="cp-sim-breakdown-title">Calculation breakdown</h4>
        <ul className="cp-sim-steps">
          {!loading
            ? result.steps.map((s) => (
                <li key={`${s.label}-${s.detail}`}>
                  <strong>{s.label}</strong>
                  <span>{s.detail}</span>
                  <span>₹{Math.round(s.amount).toLocaleString()}</span>
                </li>
              ))
            : null}
          <li className="cp-sim-steps__final">
            <strong>Final payout</strong>
            <span>{employee} · {period}</span>
            <span>₹{loading ? "…" : Math.round(result.total).toLocaleString()}</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

function RowMenu({ plan, busy, onClone, onArchive, onSimulate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const cv = plan.current_version;

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="cp-grid-menu" ref={ref}>
      <button
        type="button"
        className="cp-grid-menu__btn"
        aria-label="More actions"
        aria-expanded={open}
        disabled={busy}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
      >
        ⋮
      </button>
      {open ? (
        <ul className="cp-grid-menu__list" role="menu">
          <li>
            <Link to={`/comp-plans/${plan.id}/versions`} onClick={() => setOpen(false)}>
              Compare
            </Link>
          </li>
          <li>
            <button
              type="button"
              disabled={!cv?.id || busy}
              onClick={() => {
                setOpen(false);
                onClone?.(plan);
              }}
            >
              Clone
            </button>
          </li>
          <li>
            <Link to={`/comp-plans/${plan.id}/versions`} onClick={() => setOpen(false)}>
              Publish
            </Link>
          </li>
          <li>
            <button
              type="button"
              disabled={!cv?.id || busy || cv?.status === "Archived"}
              onClick={() => {
                setOpen(false);
                onArchive?.(plan);
              }}
            >
              Archive
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}

function ExpandedDetails({ plan }) {
  const cv = plan.current_version;
  const coverage = plan.coverage || {};
  const byKey = Object.fromEntries((plan.components || []).map((c) => [c.key, c]));
  const effective = cv
    ? formatEffectivePeriodShort(cv.effective_from, cv.effective_to)
    : formatEffectivePeriodShort(plan.effective_start_date, plan.effective_end_date);

  return (
    <div className="cp-grid-expand">
      <div className="cp-grid-expand__col">
        <h4>Overview</h4>
        <dl className="cp-grid-expand__dl">
          <div>
            <dt>Employees</dt>
            <dd>{plan.participant_count ?? coverage.employees_assigned ?? 0}</dd>
          </div>
          <div>
            <dt>Departments</dt>
            <dd>{coverage.department_count ?? coverage.departments?.length ?? 0}</dd>
          </div>
          <div>
            <dt>Regions</dt>
            <dd>{coverage.region_count ?? coverage.regions?.length ?? 0}</dd>
          </div>
          <div>
            <dt>Territories</dt>
            <dd>{coverage.territories?.length ?? 0}</dd>
          </div>
        </dl>
      </div>
      <div className="cp-grid-expand__col">
        <h4>Configuration Health</h4>
        <ul className="cp-grid-expand__pills">
          {COMPONENT_PILLS.map((item) => {
            const ok = Boolean(byKey[item.key]?.configured);
            return (
              <li key={item.key} className={ok ? "ok" : "warn"}>
                {ok ? "✓" : "⚠"} {item.short}
              </li>
            );
          })}
        </ul>
      </div>
      <div className="cp-grid-expand__col">
        <h4>Version</h4>
        <dl className="cp-grid-expand__dl">
          <div>
            <dt>Current</dt>
            <dd>{displayVersionLabel(plan)}</dd>
          </div>
          <div>
            <dt>Effective</dt>
            <dd>{effective}</dd>
          </div>
        </dl>
        <h4>Governance</h4>
        <dl className="cp-grid-expand__dl">
          <div>
            <dt>Owner</dt>
            <dd>{plan.owner || "—"}</dd>
          </div>
          <div>
            <dt>Approver</dt>
            <dd>{plan.approver || "—"}</dd>
          </div>
          <div>
            <dt>Approval</dt>
            <dd>{plan.approval_status || plan.calculation_status?.approval_status || "—"}</dd>
          </div>
        </dl>
      </div>
      <div className="cp-grid-expand__col">
        <h4>Recent Activity</h4>
        <dl className="cp-grid-expand__dl">
          <div>
            <dt>Created</dt>
            <dd>
              {plan.created_at ? new Date(plan.created_at).toLocaleDateString() : "—"}
            </dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>
              {plan.last_modified_at
                ? new Date(plan.last_modified_at).toLocaleDateString()
                : plan.updated_at
                  ? new Date(plan.updated_at).toLocaleDateString()
                  : "—"}
            </dd>
          </div>
          <div>
            <dt>Published</dt>
            <dd>{cv?.status === "Published" ? "Yes" : "—"}</dd>
          </div>
        </dl>
        <Link className="btn-primary" to={`/comp-plans/${plan.id}/overview`}>
          Open Workspace
        </Link>
      </div>
    </div>
  );
}

function CompPlansDataGrid({
  plans,
  loading,
  total,
  page,
  pageSize,
  onPageChange,
  selectedIds,
  onSelectionChange,
  expandedId,
  onExpand,
  busyId,
  onClone,
  onArchive,
  focusPlanIds,
  onBulkArchive,
  onBulkExport,
  onBulkCompare,
  onBulkSimulate,
}) {
  const [simPlan, setSimPlan] = useState(null);
  const allSelected = plans.length > 0 && plans.every((p) => selectedIds.has(p.id));
  const someSelected = selectedIds.size > 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const toggleAll = () => {
    if (allSelected) {
      onSelectionChange(new Set());
    } else {
      onSelectionChange(new Set(plans.map((p) => p.id)));
    }
  };

  const toggleOne = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onSelectionChange(next);
  };

  return (
    <section className="cp-ops-grid" aria-label="Plan management">
      {someSelected ? (
        <div className="cp-bulk-bar" role="toolbar" aria-label="Bulk actions">
          <span className="cp-bulk-bar__count">{selectedIds.size} selected</span>
          <button type="button" className="btn-secondary" onClick={() => onBulkCompare?.(selectedIds)}>
            Compare Plans
          </button>
          <button type="button" className="btn-secondary" onClick={() => onBulkSimulate?.(selectedIds)}>
            Run Simulation
          </button>
          <button type="button" className="btn-secondary" onClick={() => onBulkExport?.(selectedIds)}>
            Export
          </button>
          <button type="button" className="btn-secondary" onClick={() => onBulkArchive?.(selectedIds)}>
            Archive
          </button>
          <button type="button" className="cp-btn-ghost" onClick={() => onSelectionChange(new Set())}>
            Clear
          </button>
        </div>
      ) : null}

      <div className="cp-ops-grid__wrap">
        <table className="cp-ops-table">
          <thead>
            <tr>
              <th className="cp-ops-table__check">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  aria-label="Select all on page"
                />
              </th>
              <th>Plan</th>
              <th>Status</th>
              <th>Health</th>
              <th>Calculation</th>
              <th>Employees</th>
              <th>Est. Commission</th>
              <th>Effective</th>
              <th>Owner</th>
              <th>Modified</th>
              <th className="cp-ops-table__actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && plans.length === 0 ? (
              <tr>
                <td colSpan={11} className="cp-ops-table__empty">
                  Loading plans…
                </td>
              </tr>
            ) : plans.length === 0 ? (
              <tr>
                <td colSpan={11} className="cp-ops-table__empty">
                  No plans match your filters.
                </td>
              </tr>
            ) : (
              plans.map((plan) => {
                const cv = plan.current_version;
                const health = plan.health || {};
                const calc = calcBadge(plan.calculation_status);
                const ops = plan.ops_metrics || {};
                const employees = plan.participant_count ?? plan.coverage?.employees_assigned ?? 0;
                const statusLabel =
                  cv?.status === "Published" ? "Published" : cv?.status || plan.status;
                const effective = cv
                  ? formatEffectivePeriodShort(cv.effective_from, cv.effective_to)
                  : formatEffectivePeriodShort(plan.effective_start_date, plan.effective_end_date);
                const focused = focusPlanIds?.has?.(plan.id);
                const expanded = expandedId === plan.id;
                const est = ops.estimated_monthly_commission ?? ops.average_commission;

                return (
                  <Fragment key={plan.id}>
                    <tr
                      className={`cp-ops-table__row${expanded ? " is-expanded" : ""}${
                        focused ? " is-focused" : ""
                      }`}
                      onClick={() => onExpand(expanded ? null : plan.id)}
                    >
                      <td
                        className="cp-ops-table__check"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.has(plan.id)}
                          onChange={() => toggleOne(plan.id)}
                          aria-label={`Select ${plan.plan_name}`}
                        />
                      </td>
                      <td>
                        <div className="cp-ops-table__plan">
                          <strong>{plan.plan_name}</strong>
                          <span>
                            {plan.plan_type_label || planTypeLabel(plan)}
                            {plan.role ? ` · ${plan.role}` : ""}
                            {plan.business_group ? ` · ${plan.business_group}` : ""}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`cp-ops-badge ${planStatusClass(statusLabel)}`}>
                          {statusLabel}
                        </span>
                      </td>
                      <td>
                        <span className={`cp-ops-badge cp-ops-badge--${health.level || "warning"}`}>
                          {health.score ?? "—"}% · {healthLabel(health.level)}
                        </span>
                      </td>
                      <td>
                        <span className={`cp-ops-badge cp-ops-badge--calc-${calc.cls}`}>
                          {calc.text}
                        </span>
                      </td>
                      <td>{Number(employees).toLocaleString()}</td>
                      <td>
                        {est != null && est !== "" ? `₹${formatMoney(est)}` : "—"}
                      </td>
                      <td>{effective}</td>
                      <td>{plan.owner || "—"}</td>
                      <td>
                        {plan.last_modified_at
                          ? new Date(plan.last_modified_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="cp-ops-table__actions" onClick={(e) => e.stopPropagation()}>
                        <div className="cp-ops-table__action-row">
                          <Link className="cp-ops-link" to={`/comp-plans/${plan.id}/overview`}>
                            Open
                          </Link>
                          <button
                            type="button"
                            className="cp-ops-link"
                            onClick={() => setSimPlan(plan)}
                          >
                            Simulate
                          </button>
                          <RowMenu
                            plan={plan}
                            busy={busyId === plan.id}
                            onClone={onClone}
                            onArchive={onArchive}
                            onSimulate={() => setSimPlan(plan)}
                          />
                        </div>
                      </td>
                    </tr>
                    {expanded ? (
                      <tr className="cp-ops-table__detail-row">
                        <td colSpan={11}>
                          <ExpandedDetails plan={plan} />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {total > pageSize ? (
        <div className="cp-pagination">
          <button
            type="button"
            className="btn-secondary"
            disabled={page <= 1 || loading}
            onClick={() => onPageChange(Math.max(1, page - 1))}
          >
            Previous
          </button>
          <span className="cp-pagination__meta">
            Page {page} of {totalPages} · {total.toLocaleString()} plans
          </span>
          <button
            type="button"
            className="btn-secondary"
            disabled={page >= totalPages || loading}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </button>
        </div>
      ) : (
        <p className="cp-ops-grid__count">
          {loading ? "Updating…" : `${total.toLocaleString()} plan${total === 1 ? "" : "s"}`}
        </p>
      )}

      {simPlan ? (
        <SimulateCommissionModal plan={simPlan} onClose={() => setSimPlan(null)} />
      ) : null}
    </section>
  );
}

export default CompPlansDataGrid;
