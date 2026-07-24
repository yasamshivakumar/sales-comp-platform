import { useMemo, useState } from "react";

function buildMultiLine(series, keys, width, height, pad = 18) {
  const values = [];
  keys.forEach((k) => {
    (series || []).forEach((r) => values.push(Number(r[k] ?? 0)));
  });
  const max = Math.max(...values, 1);
  const min = 0;
  const range = max - min || 1;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const paths = {};
  keys.forEach((k) => {
    const pts = (series || []).map((r, i) => {
      const v = Number(r[k] ?? 0);
      const x = pad + (i / Math.max((series || []).length - 1, 1)) * innerW;
      const y = pad + innerH - ((v - min) / range) * innerH;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    });
    paths[k] = pts.join(" ");
  });
  return { paths, max };
}

const COLORS = {
  revenue: "#1e3a5f",
  commission: "#0f766e",
  payout: "#b45309",
};

function CommandCenterCharts({ series, currency, costRatio, period, onPeriodChange }) {
  const [metrics, setMetrics] = useState({
    revenue: true,
    commission: true,
    payout: false,
  });

  const activeKeys = useMemo(
    () => Object.keys(metrics).filter((k) => metrics[k]),
    [metrics]
  );

  const { paths } = useMemo(
    () => buildMultiLine(series || [], activeKeys.length ? activeKeys : ["revenue"], 720, 220),
    [series, activeKeys]
  );

  const has = (series || []).some(
    (r) => (r.revenue || r.sales || 0) > 0 || (r.commission || 0) > 0
  );

  const ratioStatus =
    costRatio == null
      ? { label: "—", tone: "neutral" }
      : costRatio < 5
        ? { label: "Healthy", tone: "good" }
        : costRatio < 12
          ? { label: "Monitor", tone: "warn" }
          : { label: "Elevated", tone: "bad" };

  const toggle = (key) => setMetrics((m) => ({ ...m, [key]: !m[key] }));

  return (
    <section className="ecc-perf">
      <div className="ecc-panel ecc-perf__chart">
        <div className="ecc-panel__head">
          <h2>Revenue vs Commission Trend</h2>
          <div className="ecc-seg">
            {[
              ["monthly", "Month"],
              ["quarterly", "Quarter"],
              ["annual", "Year"],
            ].map(([val, label]) => (
              <button
                key={val}
                type="button"
                className={period === val ? "is-active" : ""}
                onClick={() => onPeriodChange?.(val)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="ecc-metric-toggles">
          {[
            ["revenue", "Revenue"],
            ["commission", "Commission"],
            ["payout", "Payout"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={metrics[key] ? "is-on" : ""}
              style={{ "--tone": COLORS[key] }}
              onClick={() => toggle(key)}
            >
              <i />
              {label}
            </button>
          ))}
        </div>
        {!has ? (
          <p className="ecc-quiet">No trend data for this period</p>
        ) : (
          <>
            <svg viewBox="0 0 720 220" className="ecc-line-chart" preserveAspectRatio="none">
              {[0, 1, 2, 3].map((i) => (
                <line
                  key={i}
                  x1="18"
                  x2="702"
                  y1={18 + i * 50}
                  y2={18 + i * 50}
                  stroke="#e8edf3"
                  strokeWidth="1"
                />
              ))}
              {activeKeys.map((k) => (
                <path
                  key={k}
                  d={paths[k]}
                  fill="none"
                  stroke={COLORS[k]}
                  strokeWidth="2.25"
                />
              ))}
            </svg>
            <div className="ecc-chart-labels">
              {(series || []).map((r) => (
                <span key={r.period || r.label}>{r.label || r.period}</span>
              ))}
            </div>
            <p className="ecc-quiet">{currency}</p>
          </>
        )}
      </div>

      <aside className="ecc-panel ecc-ratio">
        <h2>Commission Cost Ratio</h2>
        <div className={`ecc-ratio__value tone-${ratioStatus.tone}`}>
          {costRatio != null ? `${costRatio}%` : "—"}
        </div>
        <div className={`ecc-ratio__status tone-${ratioStatus.tone}`}>
          {ratioStatus.label}
        </div>
        <p className="ecc-quiet">Commission as % of revenue</p>
        <div className="ecc-ratio__gauge" aria-hidden>
          <div
            className="ecc-ratio__fill"
            style={{ width: `${Math.min(((costRatio || 0) / 20) * 100, 100)}%` }}
          />
        </div>
      </aside>
    </section>
  );
}

export default CommandCenterCharts;
