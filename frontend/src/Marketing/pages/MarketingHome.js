import { PRODUCT_AREAS, SOLUTIONS_BY_FUNCTION } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import {
  HeroDashboardVisual,
  PlatformDiagram,
} from "../MarketingVisuals";
import MarketingCta from "./MarketingCta";

function MarketingHome() {
  const { showDemo, showProducts, showProduct, showTeam } = useMarketingNav();

  return (
    <>
      <section className="marketing-hero" id="home">
        <div className="marketing-hero__inner marketing-hero__inner--split">
          <div className="marketing-hero__copy">
            <p className="marketing-kicker marketing-kicker--light">Sales compensation platform</p>
            <h1>Plans, orders, commissions, and payroll — in one place</h1>
            <p className="marketing-hero__lead">
              Incentra is a multi-tenant SaaS platform for compensation plan setup, order
              ingestion, monthly commission calculation, finance approval, and payroll CSV
              export. Built for finance, compensation, and revenue operations teams that need
              a clear system of record instead of spreadsheets.
            </p>
            <div className="marketing-hero__actions">
              <button type="button" className="marketing-btn marketing-btn--primary" onClick={showDemo}>
                Request demo
              </button>
              <button
                type="button"
                className="marketing-btn marketing-btn--secondary marketing-btn--on-dark"
                onClick={showProducts}
              >
                Explore product
              </button>
            </div>
          </div>
          <HeroDashboardVisual />
        </div>
      </section>

      <section className="marketing-band marketing-band--unified">
        <div className="marketing-band__inner marketing-band__inner--split">
          <div>
            <p className="marketing-kicker marketing-kicker--light">What Incentra does today</p>
            <h2>One platform for your compensation workflow</h2>
            <p className="marketing-band__lead">
              Each organization gets isolated data, role-based access, and a single path from
              participant setup through approved payouts. Everything on this site maps to live
              product modules.
            </p>
          </div>
          <PlatformDiagram />
        </div>
      </section>

      <section className="marketing-section marketing-section--wash" id="product-modules">
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">Product</p>
          <h2>Explore by module</h2>
        </div>
        <div className="marketing-card-grid">
          {PRODUCT_AREAS.map((area) => (
            <button
              key={area.slug}
              type="button"
              className={`marketing-card-link marketing-card-link--${area.slug}`}
              onClick={() => showProduct(area.slug)}
            >
              <span className="marketing-card-link__label">{area.label}</span>
              <h3>{area.headline}</h3>
              <p>{area.summary}</p>
              <span className="marketing-card-link__arrow">Learn more →</span>
            </button>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section--wash">
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">Teams</p>
          <h2>Built for every stakeholder</h2>
        </div>
        <div className="marketing-card-grid marketing-card-grid--teams">
          {SOLUTIONS_BY_FUNCTION.map((team) => (
            <button
              key={team.slug}
              type="button"
              className="marketing-card-link"
              onClick={() => showTeam(team.slug)}
            >
              <span className="marketing-card-link__label">{team.label}</span>
              <h3>{team.title}</h3>
              <p>{team.body}</p>
              <span className="marketing-card-link__arrow">View for {team.label} →</span>
            </button>
          ))}
        </div>
      </section>

      <section className="marketing-section marketing-section--muted">
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">Platform basics</p>
          <h2>Built-in from day one</h2>
        </div>
        <div className="marketing-advantage-grid">
          <article className="marketing-advantage-card">
            <h3>Multi-tenant SaaS</h3>
            <p>Each company&apos;s data is isolated by organization with admin-scoped access.</p>
          </article>
          <article className="marketing-advantage-card">
            <h3>Role-based access</h3>
            <p>Separate experiences for admin, finance, manager, and sales rep users.</p>
          </article>
          <article className="marketing-advantage-card">
            <h3>CRM integrations</h3>
            <p>Salesforce, HubSpot, and Zoho connectors for order sync.</p>
          </article>
          <article className="marketing-advantage-card">
            <h3>Production operations</h3>
            <p>Health checks, audit logs, and documented deploy runbooks.</p>
          </article>
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingHome;
