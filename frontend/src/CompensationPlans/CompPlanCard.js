import { useEffect, useMemo, useRef, useState } from "react";
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
  { key: "rate_tables", short: "Rates", href: "rates" },
  { key: "eligibility", short: "Eligibility", href: "eligibility" },
  { key: "participants", short: "Participants", href: "participants" },
  { key: "rules", short: "Rules", href: "rules" },
  { key: "monthly_quotas", short: "Quotas", href: "quotas" },
];

function healthStatusLabel(level) {
  if (level === "healthy") return "Healthy";
  if (level === "critical") return "Critical Attention";
  return "Review Required";
}

function issueShortLabels(byKey, missing) {
  const fromComponents = COMPONENT_PILLS.filter((c) => !byKey[c.key]?.configured).map(
    (c) => `${c.short} Missing`
  );
  if (fromComponents.length) return fromComponents.slice(0, 3);
  return (missing || []).slice(0, 3);
}

function primaryBlockerAction(byKey, calc) {
  if (!byKey.participants?.configured) {
    return { reason: "No Participants", label: "Assign Employees", href: "participants" };
  }
  if (!byKey.rate_tables?.configured) {
    return { reason: "Missing Rate Tables", label: "Configure Rates", href: "rates" };
  }
  if (!byKey.eligibility?.configured) {
    return { reason: "Missing Eligibility", label: "Configure Eligibility", href: "eligibility" };
  }
  if (!byKey.rules?.configured) {
    return { reason: "Missing Rules", label: "Configure Rules", href: "rules" };
  }
  if (!byKey.monthly_quotas?.configured) {
    return { reason: "Missing Quotas", label: "Configure Quotas", href: "quotas" };
  }
  const reason = calc?.reasons?.[0] || "Configuration incomplete";
  return { reason, label: "Open Workspace", href: "overview" };
}

function formatCalcDay(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return "Today";
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function PlanIcon({ planType }) {
  const letter = String(planType || "C").charAt(0).toUpperCase();
  return (
    <span className="cp-ecard__icon" aria-hidden="true">
      {letter}
    </span>
  );
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

function SimulateModal({ plan, onClose }) {
  const [amount, setAmount] = useState("500000");
  const [detail, setDetail] = useState(plan);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError("");
      try {
        const res = await api.get(`compensation-plans/${plan.id}/`);
        if (!cancelled) setDetail(res.data);
      } catch {
        if (!cancelled) {
          setDetail(plan);
          setLoadError("Using catalog rates (detail unavailable).");
        }
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
      <div className="cp-sim-modal">
        <div className="cp-sim-modal__head">
          <h3 id="cp-sim-title">Simulate Commission</h3>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="cp-tab-lead">
          Test payout for <strong>{plan.plan_name}</strong> before publishing.
        </p>
        {loadError ? <p className="muted-mini">{loadError}</p> : null}
        <label className="cp-sim-field">
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
        <div className="cp-sim-result">
          <span className="cp-card__label">Expected commission</span>
          <strong>{loading ? "…" : `₹${Math.round(result.total).toLocaleString()}`}</strong>
        </div>
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
        </ul>
      </div>
    </div>
  );
}

function ActionsMenu({ plan, busy, onClone, onArchive, onSimulate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const cv = plan.current_version;

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="cp-card-menu" ref={ref}>
      <button
        type="button"
        className="cp-ecard__more"
        aria-label="More actions"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
      >
        ⋮
      </button>
      {open ? (
        <ul className="cp-card-menu__list" role="menu">
          <li role="none">
            <Link role="menuitem" to={`/comp-plans/${plan.id}/rules`} onClick={() => setOpen(false)}>
              Configure Rules
            </Link>
          </li>
          <li role="none">
            <Link
              role="menuitem"
              to={`/comp-plans/${plan.id}/participants`}
              onClick={() => setOpen(false)}
            >
              Assign Employees
            </Link>
          </li>
          <li role="none">
            <Link role="menuitem" to={`/comp-plans/${plan.id}/versions`} onClick={() => setOpen(false)}>
              Compare Version
            </Link>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onSimulate?.();
              }}
            >
              Simulate Commission
            </button>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
              disabled={!cv?.id || busy}
              onClick={() => {
                setOpen(false);
                onClone?.(plan);
              }}
            >
              Clone
            </button>
          </li>
          <li role="none">
            <Link role="menuitem" to={`/comp-plans/${plan.id}/versions`} onClick={() => setOpen(false)}>
              Publish
            </Link>
          </li>
          <li role="none">
            <button
              type="button"
              role="menuitem"
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

function CompPlanCard({ plan, onClone, onArchive, busy }) {
  const [showSim, setShowSim] = useState(false);
  const [showPillDetail, setShowPillDetail] = useState(false);
  const cv = plan.current_version;
  const coverage = plan.coverage || {};
  const health = plan.health || {};
  const ops = plan.ops_metrics || {};
  const calc = plan.calculation_status || {};
  const components = plan.components || [];
  const byKey = Object.fromEntries(components.map((c) => [c.key, c]));
  const score = health.score ?? 0;
  const level = health.level || "warning";
  const effective = cv
    ? formatEffectivePeriodShort(cv.effective_from, cv.effective_to)
    : formatEffectivePeriodShort(plan.effective_start_date, plan.effective_end_date);
  const statusLabel = cv?.status === "Published" ? "Published" : cv?.status || plan.status;
  const issues = issueShortLabels(byKey, health.missing);
  const previousCount = Math.max(0, (plan.versions_preview?.length || 0) - 1);
  const blocked = calc.status === "blocked";
  const ready = calc.status === "ready";
  const blocker = blocked ? primaryBlockerAction(byKey, calc) : null;
  const lastCalc = formatCalcDay(ops.last_calculation);
  const typeLabel = plan.plan_type_label || planTypeLabel(plan);
  const metaLine = [plan.role, plan.business_group].filter(Boolean).join(" | ");

  return (
    <article
      className={`cp-ecard cp-ecard--${level}${blocked ? " cp-ecard--blocked" : ""}`}
      aria-labelledby={`plan-card-${plan.id}`}
    >
      <header className="cp-ecard__header">
        <div className="cp-ecard__identity">
          <PlanIcon planType={typeLabel} />
          <div className="cp-ecard__titles">
            <h3 id={`plan-card-${plan.id}`} className="cp-ecard__name">
              {plan.plan_name}
            </h3>
            <p className="cp-ecard__type">{typeLabel}</p>
            {metaLine ? <p className="cp-ecard__meta">{metaLine}</p> : null}
          </div>
        </div>
        <div className="cp-ecard__badges">
          <span className={`cp-ecard__badge ${planStatusClass(statusLabel)}`}>{statusLabel}</span>
          <span className={`cp-ecard__badge cp-ecard__badge--score cp-ecard__badge--${level}`}>
            {score}%
          </span>
          <span className={`cp-ecard__badge cp-ecard__badge--calc cp-ecard__badge--calc-${calc.status || "pending"}`}>
            {blocked ? "⚠ Blocked" : ready ? "Ready" : calc.label || "Pending"}
          </span>
        </div>
      </header>

      <section className="cp-ecard__health" aria-label="Compensation readiness">
        <div className="cp-ecard__health-top">
          <span>Compensation Readiness</span>
          <strong>{score}%</strong>
        </div>
        <div
          className="cp-ecard__bar"
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span className={`cp-ecard__bar-fill cp-ecard__bar-fill--${level}`} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
        </div>
        <div className="cp-ecard__health-foot">
          <span className={`cp-ecard__status-text cp-ecard__status-text--${level}`}>
            {healthStatusLabel(level)}
          </span>
          {issues.length ? (
            <span className="cp-ecard__issues">{issues.join(" · ")}</span>
          ) : (
            <span className="cp-ecard__issues cp-ecard__issues--ok">No open issues</span>
          )}
        </div>
      </section>

      {blocked && blocker ? (
        <div className="cp-ecard__callout cp-ecard__callout--blocked">
          <div>
            <strong>Calculation Blocked</strong>
            <span>Reason: {blocker.reason}</span>
          </div>
          <Link className="cp-ecard__callout-btn" to={`/comp-plans/${plan.id}/${blocker.href}`}>
            {blocker.label}
          </Link>
        </div>
      ) : ready ? (
        <div className="cp-ecard__callout cp-ecard__callout--ready">
          <strong>Ready for Calculation</strong>
          <span>
            {lastCalc ? `Last successful calculation: ${lastCalc}` : "Awaiting first calculation run"}
          </span>
        </div>
      ) : null}

      <section className="cp-ecard__metrics" aria-label="Business coverage">
        <div>
          <strong>{plan.participant_count ?? coverage.employees_assigned ?? 0}</strong>
          <span>Employees</span>
        </div>
        <div>
          <strong>{coverage.region_count ?? coverage.regions?.length ?? 0}</strong>
          <span>Regions</span>
        </div>
        <div>
          <strong>{coverage.territories?.length ?? 0}</strong>
          <span>Territories</span>
        </div>
        <div>
          <strong>{coverage.department_count ?? coverage.departments?.length ?? 0}</strong>
          <span>Departments</span>
        </div>
      </section>

      <section className="cp-ecard__pills-wrap" aria-label="Component health">
        <div className="cp-ecard__pills">
          {COMPONENT_PILLS.map((item) => {
            const ok = Boolean(byKey[item.key]?.configured);
            return (
              <Link
                key={item.key}
                className={`cp-ecard__pill ${ok ? "cp-ecard__pill--ok" : "cp-ecard__pill--warn"}`}
                to={`/comp-plans/${plan.id}/${item.href}`}
                title={ok ? `${item.short} configured` : `${item.short} needs attention`}
              >
                <span aria-hidden="true">{ok ? "✓" : "⚠"}</span>
                {item.short}
              </Link>
            );
          })}
        </div>
        <button
          type="button"
          className="cp-ecard__pill-toggle"
          aria-expanded={showPillDetail}
          onClick={() => setShowPillDetail((v) => !v)}
        >
          {showPillDetail ? "Hide details" : "Details"}
        </button>
        {showPillDetail ? (
          <ul className="cp-ecard__pill-detail">
            {COMPONENT_PILLS.map((item) => {
              const row = byKey[item.key];
              return (
                <li key={item.key}>
                  <span>{item.short}</span>
                  <span className={row?.configured ? "cp-ecard__ok" : "cp-ecard__warn"}>
                    {row?.configured ? "Configured" : "Missing"}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : null}
      </section>

      <section className="cp-ecard__finance" aria-label="Financial impact">
        <div className="cp-ecard__finance-hero">
          <span>Estimated Monthly Commission</span>
          <strong>
            {ops.estimated_monthly_commission != null || ops.average_commission != null
              ? `₹${formatMoney(ops.estimated_monthly_commission ?? ops.average_commission)}`
              : "—"}
          </strong>
        </div>
        <div className="cp-ecard__finance-row">
          <div>
            <span>Last Calculation</span>
            <strong>{lastCalc || "—"}</strong>
          </div>
          <div>
            <span>Transactions</span>
            <strong>{(ops.transactions_processed || 0).toLocaleString()}</strong>
          </div>
        </div>
      </section>

      <section className="cp-ecard__version">
        <div>
          <span>Current Version</span>
          <strong>{displayVersionLabel(plan)}</strong>
        </div>
        <div>
          <span>Effective</span>
          <strong>{effective}</strong>
        </div>
        <Link className="cp-ecard__prev" to={`/comp-plans/${plan.id}/versions`}>
          Previous versions
          <strong>{previousCount > 0 ? `+${previousCount}` : "—"}</strong>
        </Link>
      </section>

      <footer className="cp-ecard__footer">
        <Link className="btn-primary" to={`/comp-plans/${plan.id}/overview`}>
          Open Workspace
        </Link>
        <ActionsMenu
          plan={plan}
          busy={busy}
          onClone={onClone}
          onArchive={onArchive}
          onSimulate={() => setShowSim(true)}
        />
      </footer>

      {showSim ? <SimulateModal plan={plan} onClose={() => setShowSim(false)} /> : null}
    </article>
  );
}

export default CompPlanCard;
