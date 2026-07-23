import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import TierForm from "../TierForm";
import TierList from "../TierList";
import LookupTierForm from "../LookupTierForm";
import LookupTierList from "../LookupTierList";
import { calculationMethodLabel } from "../compPlanUtils";

function formatAmount(value) {
  if (value == null || value === "") return "∞";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  if (n >= 1000) return `${Math.round(n / 1000)}K`;
  return String(n);
}

function calcMode(plan) {
  const type = plan.commission_table_type;
  if (type === "MARGINAL" || plan.tier_calculation_method === "marginal") {
    return { label: "Progressive (marginal)", mode: "progressive" };
  }
  if (type === "HIGHEST" || type === "RATE" || type === "FLAT" || type === "LOOKUP") {
    return { label: "Cliff (landing tier)", mode: "cliff" };
  }
  return { label: calculationMethodLabel(plan), mode: "cliff" };
}

function cumulativeExamples(bands, mode) {
  if (!bands.length) return [];
  const samples = [25000, 75000, 150000];
  return samples.map((sales) => {
    let commission = 0;
    let applied = "—";
    if (mode === "progressive") {
      let prev = 0;
      for (const band of bands) {
        const from = Number(band.from ?? 0);
        const to = band.to == null ? Infinity : Number(band.to);
        const rate = Number(band.rateNum ?? 0);
        const sliceStart = Math.max(prev, from);
        const sliceEnd = Math.min(sales, to);
        if (sliceEnd > sliceStart) {
          commission += ((sliceEnd - sliceStart) * rate) / 100;
        }
        prev = to === Infinity ? sales : to;
        if (sales <= to) {
          applied = band.rate;
          break;
        }
      }
    } else {
      const band =
        bands.find((b) => {
          const from = Number(b.from ?? 0);
          const to = b.to == null ? Infinity : Number(b.to);
          return sales >= from && sales <= to;
        }) || bands[bands.length - 1];
      const rate = Number(band?.rateNum ?? 0);
      commission = (sales * rate) / 100;
      applied = band?.rate || "—";
    }
    return {
      sales,
      applied,
      commission: Math.round(commission * 100) / 100,
    };
  });
}

function RateBandsVisual({ plan }) {
  const type = plan.commission_table_type;
  const { label: modeLabel, mode } = calcMode(plan);
  let bands = [];
  if (type === "FLAT") {
    bands = (plan.sc_flat_rate_tables || []).map((row) => ({
      id: row.id,
      label: "Flat",
      range: "All amounts",
      from: 0,
      to: null,
      rate: `${row.flat_rate ?? row.commission_rate ?? 0}%`,
      rateNum: Number(row.flat_rate ?? row.commission_rate ?? 0),
    }));
  } else if (type === "LOOKUP") {
    bands = (plan.sc_lookup_tables || []).map((row) => ({
      id: row.id,
      label:
        [row.product_name, row.service_name, row.distribution].filter(Boolean).join(" / ") ||
        row.tier_name ||
        "Lookup",
      range: `${formatAmount(row.from_amount)}–${formatAmount(row.to_amount)}`,
      from: row.from_amount,
      to: row.to_amount,
      rate: `${row.commission_rate ?? 0}%`,
      rateNum: Number(row.commission_rate ?? 0),
    }));
  } else {
    bands = (plan.sc_rate_tables || []).map((row) => ({
      id: row.id,
      label: row.tier_name || "Band",
      range: `${formatAmount(row.from_amount)}–${formatAmount(row.to_amount)}`,
      from: row.from_amount,
      to: row.to_amount,
      rate: `${row.commission_rate ?? 0}%`,
      rateNum: Number(row.commission_rate ?? 0),
      bonus: row.bonus_amount,
    }));
  }

  const examples = cumulativeExamples(bands, mode);

  if (!bands.length) {
    return <p className="cp-tab-lead">No rate bands yet.</p>;
  }

  return (
    <div className="cp-rate-visual">
      <p className="cp-tab-lead">
        Calculation method: <strong>{modeLabel}</strong>
      </p>
      <div className="cp-rate-bands" aria-label="Rate bands">
        {bands.map((band) => (
          <div key={band.id || `${band.label}-${band.range}`} className="cp-rate-band">
            <div className="cp-rate-band__range">{band.range}</div>
            <div className="cp-rate-band__bar" />
            <div className="cp-rate-band__rate">{band.rate}</div>
            <div className="cp-rate-band__label">
              {band.label}
              {band.bonus ? ` · bonus ${band.bonus}` : ""}
            </div>
          </div>
        ))}
      </div>
      {examples.length > 0 ? (
        <div className="cp-rate-examples" aria-label="Cumulative commission examples">
          <h3 className="cp-mini-chart__title">Cumulative examples</h3>
          <div className="enterprise-table-wrap">
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>Sales amount</th>
                  <th>Applied rate</th>
                  <th>Estimated commission</th>
                </tr>
              </thead>
              <tbody>
                {examples.map((ex) => (
                  <tr key={ex.sales}>
                    <td>{ex.sales.toLocaleString()}</td>
                    <td>{ex.applied}</td>
                    <td>{ex.commission.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RatesTab() {
  const { plan, reloadPlan } = useOutletContext();
  const [editingTier, setEditingTier] = useState(null);
  const editable = !plan.current_version || plan.current_version.is_editable;
  const isLookup = plan.commission_table_type === "LOOKUP";

  const handleSaved = async () => {
    setEditingTier(null);
    await reloadPlan();
  };

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <h2 className="panel__title">Rate tables</h2>
        <p className="cp-tab-lead">
          Tier ranges, rates, and {calcMode(plan).label.toLowerCase()} examples.
          {!editable
            ? " Published versions are read-only — clone a version to edit rates."
            : null}
        </p>
        <RateBandsVisual plan={plan} />
      </section>

      {editable && (
        <section className="panel cp-tab-panel">
          <h2 className="panel__title">{editingTier ? "Edit tier" : "Add tier"}</h2>
          {isLookup ? (
            <LookupTierForm
              selectedPlan={plan}
              editingTier={editingTier}
              onTierUpdated={handleSaved}
              onCancelEdit={() => setEditingTier(null)}
            />
          ) : (
            <TierForm
              selectedPlan={plan}
              editingTier={editingTier}
              onTierUpdated={handleSaved}
              onCancelEdit={() => setEditingTier(null)}
            />
          )}
        </section>
      )}

      <section className="panel cp-tab-panel">
        <h2 className="panel__title">Tier list</h2>
        {isLookup ? (
          <LookupTierList
            selectedPlan={plan}
            onEditTier={
              editable ? (row, index) => setEditingTier({ row, index }) : undefined
            }
          />
        ) : (
          <TierList
            selectedPlan={plan}
            onEditTier={
              editable ? (row, index) => setEditingTier({ row, index }) : undefined
            }
          />
        )}
      </section>
    </div>
  );
}

export default RatesTab;
