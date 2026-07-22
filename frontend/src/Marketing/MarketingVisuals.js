export function HeroEnterpriseVisual() {
  return (
    <div className="mkt-hero-visual" aria-hidden="true">
      <div className="mkt-hero-visual__float mkt-hero-visual__float--tl">
        <span className="mkt-hero-visual__float-label">This month</span>
        <strong>$284K</strong>
        <small>+12% vs prior</small>
      </div>
      <div className="mkt-hero-visual__float mkt-hero-visual__float--br">
        <span className="mkt-hero-visual__float-label">Status</span>
        <strong>Approved</strong>
        <small>Ready for payroll</small>
      </div>
      <div className="mkt-hero-visual__frame">
        <div className="mkt-hero-visual__chrome">
          <span />
          <span />
          <span />
          <span className="mkt-hero-visual__title">Incentra workspace</span>
        </div>
        <div className="mkt-hero-visual__body">
          <div className="mkt-hero-visual__sidebar">
            <span className="mkt-hero-visual__nav mkt-hero-visual__nav--active" />
            <span className="mkt-hero-visual__nav" />
            <span className="mkt-hero-visual__nav" />
            <span className="mkt-hero-visual__nav" />
          </div>
          <div className="mkt-hero-visual__main">
            <div className="mkt-hero-visual__kpis">
              <div className="mkt-hero-visual__kpi">
                <span>Plans</span>
                <strong>Active</strong>
              </div>
              <div className="mkt-hero-visual__kpi">
                <span>Orders</span>
                <strong>Queued</strong>
              </div>
              <div className="mkt-hero-visual__kpi mkt-hero-visual__kpi--accent">
                <span>Commissions</span>
                <strong>Approved</strong>
              </div>
            </div>
            <div className="mkt-hero-visual__chart">
              <div className="mkt-hero-visual__bar" style={{ height: "42%" }} />
              <div className="mkt-hero-visual__bar" style={{ height: "68%" }} />
              <div className="mkt-hero-visual__bar" style={{ height: "55%" }} />
              <div className="mkt-hero-visual__bar mkt-hero-visual__bar--peak" style={{ height: "88%" }} />
              <div className="mkt-hero-visual__bar" style={{ height: "61%" }} />
            </div>
            <div className="mkt-hero-visual__pipeline">
              <span className="mkt-hero-visual__step mkt-hero-visual__step--done">Success</span>
              <span className="mkt-hero-visual__arrow">→</span>
              <span className="mkt-hero-visual__step mkt-hero-visual__step--done">Calculated</span>
              <span className="mkt-hero-visual__arrow">→</span>
              <span className="mkt-hero-visual__step mkt-hero-visual__step--active">Approved</span>
              <span className="mkt-hero-visual__arrow">→</span>
              <span className="mkt-hero-visual__step">Payroll CSV</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModulePreviewPlans() {
  return (
    <div className="marketing-module-preview__panel">
      {["Rate tiers by quota band", "Flat rate tables", "SC lookup tables"].map((label, i) => (
        <div
          key={label}
          className={`marketing-module-preview__list-item${i === 0 ? " marketing-module-preview__list-item--active" : ""}`}
        >
          <span>{label}</span>
        </div>
      ))}
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
        <span>Rep</span><span>Status</span><span>Stage</span>
      </div>
      <div className="marketing-module-preview__row">
        <span>Priya S.</span>
        <span className="marketing-module-preview__badge">Approved</span>
        <span>Payroll</span>
      </div>
      <div className="marketing-module-preview__row">
        <span>James M.</span>
        <span className="marketing-module-preview__badge marketing-module-preview__badge--pending">Calculated</span>
        <span>Review</span>
      </div>
    </div>
  );
}

function ModulePreviewDashboard() {
  return (
    <div className="marketing-module-preview__panel marketing-module-preview__panel--chart">
      <div className="marketing-module-preview__mini-kpis">
        <div><span>Sales</span><strong>Period view</strong></div>
        <div><strong>Quota</strong><span>Attainment</span></div>
      </div>
      <div className="marketing-module-preview__mini-chart">
        {[40, 65, 50, 80, 58].map((h) => (
          <span key={h} style={{ height: `${h}%` }} />
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

export function TeamPersonaVisual({ label, bullets, slug = "finance" }) {
  return (
    <div className="marketing-team-visual" aria-hidden="true">
      <div className={`marketing-team-visual__card marketing-team-visual__card--${slug}`}>
        <span className="marketing-team-visual__label">{label}</span>
        <p className="marketing-team-visual__title">Key capabilities</p>
        <ul className="marketing-team-visual__checks">
          {bullets.slice(0, 4).map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
