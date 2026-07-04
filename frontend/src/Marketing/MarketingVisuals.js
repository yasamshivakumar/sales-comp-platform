export function HeroDashboardVisual() {
  return (
    <div className="marketing-hero-visual" aria-hidden="true">
      <div className="marketing-hero-visual__glow" />
      <div className="marketing-hero-visual__frame">
        <div className="marketing-hero-visual__chrome">
          <span />
          <span />
          <span />
          <span className="marketing-hero-visual__title">Incentra workspace</span>
        </div>
        <div className="marketing-hero-visual__body">
          <div className="marketing-hero-visual__sidebar">
            <span className="marketing-hero-visual__nav marketing-hero-visual__nav--active" />
            <span className="marketing-hero-visual__nav" />
            <span className="marketing-hero-visual__nav" />
            <span className="marketing-hero-visual__nav" />
          </div>
          <div className="marketing-hero-visual__main">
            <div className="marketing-hero-visual__kpis">
              <div className="marketing-hero-visual__kpi">
                <span>Plans</span>
                <strong>12</strong>
              </div>
              <div className="marketing-hero-visual__kpi">
                <span>Orders</span>
                <strong>847</strong>
              </div>
              <div className="marketing-hero-visual__kpi marketing-hero-visual__kpi--accent">
                <span>Commissions</span>
                <strong>₹24.6L</strong>
              </div>
            </div>
            <div className="marketing-hero-visual__chart">
              <div className="marketing-hero-visual__bar" style={{ height: "42%" }} />
              <div className="marketing-hero-visual__bar" style={{ height: "68%" }} />
              <div className="marketing-hero-visual__bar" style={{ height: "55%" }} />
              <div className="marketing-hero-visual__bar marketing-hero-visual__bar--peak" style={{ height: "88%" }} />
              <div className="marketing-hero-visual__bar" style={{ height: "61%" }} />
            </div>
            <div className="marketing-hero-visual__pipeline">
              <span className="marketing-hero-visual__step marketing-hero-visual__step--done">Success</span>
              <span className="marketing-hero-visual__arrow">→</span>
              <span className="marketing-hero-visual__step marketing-hero-visual__step--done">Calculated</span>
              <span className="marketing-hero-visual__arrow">→</span>
              <span className="marketing-hero-visual__step marketing-hero-visual__step--active">Approved</span>
              <span className="marketing-hero-visual__arrow">→</span>
              <span className="marketing-hero-visual__step">Payroll CSV</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PlatformDiagram() {
  return (
    <div className="marketing-platform-diagram" aria-hidden="true">
      <div className="marketing-platform-diagram__hub">Incentra</div>
      <div className="marketing-platform-diagram__spoke marketing-platform-diagram__spoke--tl">Plans</div>
      <div className="marketing-platform-diagram__spoke marketing-platform-diagram__spoke--tr">Orders</div>
      <div className="marketing-platform-diagram__spoke marketing-platform-diagram__spoke--bl">CRM</div>
      <div className="marketing-platform-diagram__spoke marketing-platform-diagram__spoke--br">Payroll</div>
      <svg className="marketing-platform-diagram__lines" viewBox="0 0 320 240">
        <line x1="160" y1="120" x2="80" y2="48" stroke="rgba(1,118,210,0.35)" strokeWidth="2" />
        <line x1="160" y1="120" x2="240" y2="48" stroke="rgba(1,118,210,0.35)" strokeWidth="2" />
        <line x1="160" y1="120" x2="80" y2="192" stroke="rgba(1,118,210,0.35)" strokeWidth="2" />
        <line x1="160" y1="120" x2="240" y2="192" stroke="rgba(1,118,210,0.35)" strokeWidth="2" />
      </svg>
    </div>
  );
}

function ModulePreviewPlans() {
  return (
    <div className="marketing-module-preview__panel">
      <div className="marketing-module-preview__row marketing-module-preview__row--head">
        <span>Tier</span><span>Rate</span><span>Amount</span>
      </div>
      <div className="marketing-module-preview__row"><span>0 – 50K</span><span>8%</span><span>—</span></div>
      <div className="marketing-module-preview__row marketing-module-preview__row--active"><span>50K – 100K</span><span>10%</span><span>—</span></div>
      <div className="marketing-module-preview__row"><span>100K+</span><span>Flat</span><span>₹12,000</span></div>
    </div>
  );
}

function ModulePreviewParticipants() {
  return (
    <div className="marketing-module-preview__panel">
      {["Priya S. · Rep", "James M. · Manager", "Alex K. · Finance"].map((name, i) => (
        <div key={name} className={`marketing-module-preview__list-item${i === 0 ? " marketing-module-preview__list-item--active" : ""}`}>
          <span>{name}</span>
        </div>
      ))}
    </div>
  );
}

function ModulePreviewCrm() {
  return (
    <div className="marketing-module-preview__panel marketing-module-preview__panel--sync">
      <div className="marketing-module-preview__crm-box">CRM deals</div>
      <div className="marketing-module-preview__sync-arrow">⇄</div>
      <div className="marketing-module-preview__crm-box marketing-module-preview__crm-box--accent">Incentra orders</div>
    </div>
  );
}

function ModulePreviewCommissions() {
  return (
    <div className="marketing-module-preview__panel">
      <div className="marketing-module-preview__row marketing-module-preview__row--head">
        <span>Rep</span><span>Status</span><span>Amount</span>
      </div>
      <div className="marketing-module-preview__row"><span>Priya S.</span><span className="marketing-module-preview__badge">Approved</span><span>₹42,500</span></div>
      <div className="marketing-module-preview__row"><span>James M.</span><span className="marketing-module-preview__badge marketing-module-preview__badge--pending">Calculated</span><span>₹18,200</span></div>
    </div>
  );
}

function ModulePreviewDashboard() {
  return (
    <div className="marketing-module-preview__panel marketing-module-preview__panel--chart">
      <div className="marketing-module-preview__mini-kpis">
        <div><span>Sales</span><strong>₹1.2Cr</strong></div>
        <div><strong>94%</strong><span>Quota</span></div>
      </div>
      <div className="marketing-module-preview__mini-chart">
        {[40, 65, 50, 80, 58].map((h, i) => (
          <span key={i} style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}

const MODULE_PREVIEWS = {
  plans: ModulePreviewPlans,
  participants: ModulePreviewParticipants,
  "crm-sync": ModulePreviewCrm,
  commissions: ModulePreviewCommissions,
  dashboard: ModulePreviewDashboard,
};

export function ModulePreviewVisual({ slug, label }) {
  const Preview = MODULE_PREVIEWS[slug] || ModulePreviewPlans;
  return (
    <div className="marketing-module-preview" aria-hidden="true">
      <div className="marketing-module-preview__frame">
        <div className="marketing-module-preview__header">
          <span>{label}</span>
        </div>
        <Preview />
      </div>
    </div>
  );
}

export function TeamPersonaVisual({ label, bullets }) {
  return (
    <div className="marketing-team-visual" aria-hidden="true">
      <div className="marketing-team-visual__card">
        <span className="marketing-team-visual__label">{label}</span>
        <ul className="marketing-team-visual__checks">
          {bullets.slice(0, 3).map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
