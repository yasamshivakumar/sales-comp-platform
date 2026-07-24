import { useMemo, useState } from "react";
import { formatMoney } from "../utils/currency";

const COLORS = {
  revenue: "#1e3a5f",
  commission: "#0f766e",
  payout: "#b45309",
  previous: "#94a3b8",
};

function buildSeriesGeometry(series, keys, width, height, pad = 28) {
  const values = [];
  keys.forEach((k) => {
    (series || []).forEach((r) => values.push(Number(r[k] ?? r.sales ?? 0)));
  });
  const max = Math.max(...values, 1);
  const min = 0;
  const range = max - min || 1;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const n = Math.max((series || []).length - 1, 1);

  const paths = {};
  const pointsByKey = {};
  keys.forEach((k) => {
    const pts = [];
    const path = (series || [])
      .map((r, i) => {
        const v = Number(r[k] ?? (k === "revenue" ? r.sales : 0) ?? 0);
        const x = pad + (i / n) * innerW;
        const y = pad + innerH - ((v - min) / range) * innerH;
        pts.push({ x, y, v, i, label: r.label || r.period });
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
    paths[k] = path;
    pointsByKey[k] = pts;
  });
  return { paths, pointsByKey, max, pad, innerW, range, min, innerH };
}

function alignPrevious(current, previous) {
  if (!previous?.length || !current?.length) return [];
  const n = current.length;
  const out = [];
  for (let i = 0; i < n; i += 1) {
    const src = previous[Math.min(i, previous.length - 1)] || {};
    out.push({
      period: current[i].period,
      label: current[i].label,
      revenue: src.revenue ?? src.sales ?? 0,
      commission: src.commission ?? 0,
      payout: src.payout ?? 0,
    });
  }
  return out;
}

function CommandCenterCharts({
  series,
  previousSeries,
  currency,
  period,
  onPeriodChange,
  rangeLabel,
}) {
  const [hover, setHover] = useState(null);
  const [compare, setCompare] = useState(true);
  const activeKeys = ["revenue", "commission", "payout"];
  const width = 960;
  const height = 360;

  const alignedPrev = useMemo(
    () => alignPrevious(series || [], previousSeries || []),
    [series, previousSeries]
  );

  const geometry = useMemo(() => {
    const combined = [...(series || [])];
    if (compare) {
      alignedPrev.forEach((r) => combined.push(r));
    }
    // Build geometry from current series but scale using combined max
    const base = buildSeriesGeometry(series || [], ["revenue", "commission", "payout"], width, height);
    if (!compare || !alignedPrev.length) return base;
    const values = combined.flatMap((r) => [
      Number(r.revenue ?? r.sales ?? 0),
      Number(r.commission ?? 0),
      Number(r.payout ?? 0),
    ]);
    const localMax = Math.max(...values, 1);
    const padLocal = 28;
    const innerWLocal = width - padLocal * 2;
    const innerH = height - padLocal * 2;
    const n = Math.max((series || []).length - 1, 1);
    const paths = {};
    const pointsByKey = {};
    ["revenue", "commission", "payout"].forEach((k) => {
      const pts = [];
      paths[k] = (series || [])
        .map((r, i) => {
          const v = Number(r[k] ?? (k === "revenue" ? r.sales : 0) ?? 0);
          const x = padLocal + (i / n) * innerWLocal;
          const y = padLocal + innerH - (v / localMax) * innerH;
          pts.push({ x, y, v, i, label: r.label || r.period });
          return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
      pointsByKey[k] = pts;
    });
    return { paths, pointsByKey, max: localMax, pad: padLocal, innerW: innerWLocal };
  }, [series, alignedPrev, compare]);

  const { paths, pointsByKey, max, pad, innerW } = geometry;

  const prevPath = useMemo(() => {
    if (!compare || !alignedPrev.length) return "";
    const localMax = max || 1;
    const innerH = height - pad * 2;
    const n = Math.max((series || []).length - 1, 1);
    return alignedPrev
      .map((r, i) => {
        const v = Number(r.revenue ?? 0);
        const x = pad + (i / n) * innerW;
        const y = pad + innerH - (v / localMax) * innerH;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [alignedPrev, compare, series, pad, innerW, max]);

  const has = (series || []).some(
    (r) => (r.revenue || r.sales || 0) > 0 || (r.commission || 0) > 0 || (r.payout || 0) > 0
  );

  const onMove = (e) => {
    if (!series?.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * width;
    const n = Math.max(series.length - 1, 1);
    const idx = Math.round(((x - pad) / innerW) * n);
    const clamped = Math.max(0, Math.min(series.length - 1, idx));
    const row = series[clamped];
    const prev = alignedPrev[clamped];
    setHover({
      idx: clamped,
      label: row.label || row.period,
      revenue: row.revenue ?? row.sales ?? 0,
      commission: row.commission ?? 0,
      payout: row.payout ?? 0,
      prevRevenue: prev?.revenue,
      x: pad + (clamped / n) * innerW,
    });
  };

  const exportCsv = () => {
    const lines = ["period,revenue,commission,payout,previous_revenue"];
    (series || []).forEach((r, i) => {
      lines.push(
        `${r.label || r.period},${r.revenue ?? r.sales ?? 0},${r.commission ?? 0},${r.payout ?? 0},${
          alignedPrev[i]?.revenue ?? ""
        }`
      );
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "performance-trend.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="ecc-panel ecc-trend">
      <div className="ecc-panel__head">
        <div>
          <h2>Performance Trend</h2>
          <p className="ecc-quiet">{rangeLabel || "Selected period"}</p>
        </div>
        <div className="ecc-trend__tools">
          <div className="ecc-seg">
            {[
              ["monthly", "Monthly"],
              ["quarterly", "Quarterly"],
              ["annual", "Yearly"],
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
          <button
            type="button"
            className={`ecc-btn ecc-btn--sm ${compare ? "is-active" : ""}`}
            onClick={() => setCompare((v) => !v)}
          >
            Previous period
          </button>
          <button type="button" className="ecc-btn ecc-btn--sm" onClick={exportCsv}>
            Export
          </button>
        </div>
      </div>

      <div className="ecc-legend-inline">
        {activeKeys.map((k) => (
          <span key={k}>
            <i style={{ background: COLORS[k] }} />
            {k.charAt(0).toUpperCase() + k.slice(1)}
          </span>
        ))}
        {compare ? (
          <span>
            <i style={{ background: COLORS.previous }} />
            Previous revenue
          </span>
        ) : null}
      </div>

      {!has ? (
        <p className="ecc-quiet">No trend data for this period</p>
      ) : (
        <div className="ecc-trend__canvas" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          <svg viewBox={`0 0 ${width} ${height}`} className="ecc-line-chart" preserveAspectRatio="none">
            {[0, 1, 2, 3, 4].map((i) => (
              <line
                key={i}
                x1={pad}
                x2={width - pad}
                y1={pad + i * ((height - pad * 2) / 4)}
                y2={pad + i * ((height - pad * 2) / 4)}
                stroke="#e8edf3"
                strokeWidth="1"
              />
            ))}
            {compare && prevPath ? (
              <path
                d={prevPath}
                fill="none"
                stroke={COLORS.previous}
                strokeWidth="2"
                strokeDasharray="5 4"
              />
            ) : null}
            {hover ? (
              <line
                x1={hover.x}
                x2={hover.x}
                y1={pad}
                y2={height - pad}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                strokeWidth="1"
              />
            ) : null}
            {activeKeys.map((k) => (
              <path key={k} d={paths[k]} fill="none" stroke={COLORS[k]} strokeWidth="2.75" />
            ))}
            {hover
              ? activeKeys.map((k) => {
                  const pt = pointsByKey[k]?.[hover.idx];
                  if (!pt) return null;
                  return <circle key={k} cx={pt.x} cy={pt.y} r="4.5" fill={COLORS[k]} />;
                })
              : null}
          </svg>
          {hover ? (
            <div className="ecc-tooltip" style={{ left: `${(hover.x / width) * 100}%` }}>
              <strong>{hover.label}</strong>
              <div>
                <span style={{ color: COLORS.revenue }}>Revenue</span>
                {formatMoney(hover.revenue, currency, { compact: true })}
              </div>
              <div>
                <span style={{ color: COLORS.commission }}>Commission</span>
                {formatMoney(hover.commission, currency, { compact: true })}
              </div>
              <div>
                <span style={{ color: COLORS.payout }}>Payout</span>
                {formatMoney(hover.payout, currency, { compact: true })}
              </div>
              {compare && hover.prevRevenue != null ? (
                <div>
                  <span style={{ color: COLORS.previous }}>Prev revenue</span>
                  {formatMoney(hover.prevRevenue, currency, { compact: true })}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
      <div className="ecc-chart-labels">
        {(series || []).map((r) => (
          <span key={r.period || r.label}>{r.label || r.period}</span>
        ))}
      </div>
      <p className="ecc-quiet ecc-trend__scale">
        Peak {formatMoney(max, currency, { compact: true })}
      </p>
    </section>
  );
}

export default CommandCenterCharts;
