import { PRODUCT_AREAS, SOLUTIONS_BY_FUNCTION } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import {
  TRUST_METRICS,
  TRUST_LOGOS,
  HOME_BENEFITS,
  HOW_IT_WORKS,
  SCREENSHOT_SECTIONS,
  TESTIMONIALS,
  FAQ_ITEMS,
} from "../marketingHomeData";
import { HeroEnterpriseVisual, ModulePreviewVisual } from "../MarketingVisuals";
import MarketingReveal from "../components/MarketingReveal";
import MarketingButton from "../components/MarketingButton";
import FaqAccordion from "../components/FaqAccordion";
import BrowserFrame from "../components/BrowserFrame";
import { MarketingIcon } from "../components/MarketingIcons";

const HERO_BADGES = [
  "Audit logs",
  "Role-based access",
  "Multi-currency",
  "CRM integrations",
];

function MarketingHome() {
  const { showDemo, showProduct, showTeam } = useMarketingNav();

  return (
    <>
      <section className="mkt-hero" id="home">
        <div className="mkt-hero__inner">
          <MarketingReveal className="mkt-hero__copy">
            <p className="mkt-hero__eyebrow">
              <span className="mkt-hero__eyebrow-dot" />
              Enterprise commission management
            </p>
            <h1>Commission operations your finance team can trust</h1>
            <p className="mkt-hero__lead">
              Incentra unifies compensation plans, order ingestion, monthly calculations,
              approvals, and payroll export — replacing spreadsheets with a secure system
              of record for global sales organizations.
            </p>
            <div className="mkt-hero__actions">
              <MarketingButton variant="primary" onClick={showDemo}>
                Request demo
              </MarketingButton>
              <MarketingButton
                variant="secondary"
                href="mailto:shivakumar@incentra.co.in?subject=Incentra%20sales%20inquiry"
              >
                Contact sales
              </MarketingButton>
            </div>
            <div className="mkt-hero__trust">
              {HERO_BADGES.map((badge) => (
                <span key={badge} className="mkt-hero__badge">
                  <MarketingIcon name="check" />
                  {badge}
                </span>
              ))}
            </div>
          </MarketingReveal>
          <MarketingReveal delay={120}>
            <HeroEnterpriseVisual />
          </MarketingReveal>
        </div>
      </section>

      <section className="mkt-section mkt-section--white" aria-label="Trust and metrics">
        <div className="mkt-section__inner">
          <MarketingReveal>
            <div className="mkt-trust__logos">
              {TRUST_LOGOS.map((logo) => (
                <span key={logo} className="mkt-trust__logo">
                  {logo}
                </span>
              ))}
            </div>
            <div className="mkt-trust__metrics">
              {TRUST_METRICS.map((metric) => (
                <div key={metric.label} className="mkt-trust__metric">
                  <strong>{metric.value}</strong>
                  <span>{metric.label}</span>
                </div>
              ))}
            </div>
          </MarketingReveal>
        </div>
      </section>

      <section className="mkt-section mkt-section--muted" id="product-modules">
        <div className="mkt-section__inner">
          <MarketingReveal className="mkt-section__head mkt-section__head--center">
            <span className="mkt-kicker">Product</span>
            <h2>Every module your compensation workflow needs</h2>
            <p className="mkt-section__lead">
              From plan design through approved payouts — each area maps to live product
              capabilities in your tenant.
            </p>
          </MarketingReveal>
          <div className="mkt-feature-grid">
            {PRODUCT_AREAS.map((area, index) => (
              <MarketingReveal key={area.slug} delay={index * 60}>
                <button
                  type="button"
                  className={`mkt-feature-card mkt-feature-card--${area.slug}`}
                  onClick={() => showProduct(area.slug)}
                >
                  <span className="mkt-feature-card__icon">
                    <MarketingIcon name={area.slug} />
                  </span>
                  <span className="mkt-feature-card__label">{area.label}</span>
                  <h3>{area.headline}</h3>
                  <p>{area.summary}</p>
                  <span className="mkt-feature-card__link">Explore module →</span>
                </button>
              </MarketingReveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mkt-section mkt-section--white">
        <div className="mkt-section__inner">
          <MarketingReveal className="mkt-section__head mkt-section__head--center">
            <span className="mkt-kicker">Why Incentra</span>
            <h2>Built for accuracy, scale, and control</h2>
            <p className="mkt-section__lead">
              Enterprise finance and RevOps teams choose a platform that keeps logic
              transparent and payouts defensible.
            </p>
          </MarketingReveal>
          <div className="mkt-benefits-grid">
            {HOME_BENEFITS.map((benefit, index) => (
              <MarketingReveal key={benefit.id} delay={index * 50}>
                <article className="mkt-benefit-card">
                  <h3>{benefit.title}</h3>
                  <p>{benefit.description}</p>
                </article>
              </MarketingReveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mkt-section mkt-section--muted">
        <div className="mkt-section__inner">
          {SCREENSHOT_SECTIONS.map((section, index) => {
            const area = PRODUCT_AREAS.find((a) => a.slug === section.id);
            const isReverse = section.align === "right";

            return (
              <MarketingReveal key={section.id}>
                <div className={`mkt-split${isReverse ? " mkt-split--reverse" : ""}`}>
                  <div className="mkt-split__copy">
                    <span className="mkt-kicker">{section.kicker}</span>
                    <h3>{section.title}</h3>
                    <p>{section.description}</p>
                    {area && (
                      <MarketingButton variant="secondary" onClick={() => showProduct(area.slug)}>
                        View {area.label}
                      </MarketingButton>
                    )}
                  </div>
                  <div className="mkt-split__visual">
                    <BrowserFrame title={`Incentra — ${area?.label || "Workspace"}`}>
                      {area && <ModulePreviewVisual slug={area.slug} label={area.label} />}
                    </BrowserFrame>
                  </div>
                </div>
              </MarketingReveal>
            );
          })}
        </div>
      </section>

      <section className="mkt-section mkt-section--white">
        <div className="mkt-section__inner">
          <MarketingReveal className="mkt-section__head mkt-section__head--center">
            <span className="mkt-kicker">How it works</span>
            <h2>From CRM deal to payroll export in four steps</h2>
          </MarketingReveal>
          <div className="mkt-steps">
            {HOW_IT_WORKS.map((step, index) => (
              <MarketingReveal key={step.title} delay={index * 70}>
                <article className="mkt-step">
                  <span className="mkt-step__num">{step.step}</span>
                  <h3>{step.title}</h3>
                  <p>{step.description}</p>
                </article>
              </MarketingReveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mkt-section mkt-section--muted" id="teams">
        <div className="mkt-section__inner">
          <MarketingReveal className="mkt-section__head mkt-section__head--center">
            <span className="mkt-kicker">Solutions</span>
            <h2>Designed for every stakeholder</h2>
            <p className="mkt-section__lead">
              Finance, compensation, RevOps, and sales each get a purpose-built experience.
            </p>
          </MarketingReveal>
          <div className="mkt-team-grid">
            {SOLUTIONS_BY_FUNCTION.map((team, index) => (
              <MarketingReveal key={team.slug} delay={index * 50}>
                <button
                  type="button"
                  className={`mkt-team-card mkt-team-card--${team.slug}`}
                  onClick={() => showTeam(team.slug)}
                >
                  <span className="mkt-team-card__label">{team.label}</span>
                  <h3>{team.title}</h3>
                  <p>{team.body}</p>
                </button>
              </MarketingReveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mkt-section mkt-section--white">
        <div className="mkt-section__inner">
          <MarketingReveal className="mkt-section__head mkt-section__head--center">
            <span className="mkt-kicker">Customers</span>
            <h2>Trusted by compensation and finance leaders</h2>
          </MarketingReveal>
          <div className="mkt-testimonials">
            {TESTIMONIALS.map((item, index) => (
              <MarketingReveal key={item.name} delay={index * 80}>
                <article className="mkt-testimonial">
                  <div className="mkt-testimonial__stars" aria-label={`${item.rating} out of 5 stars`}>
                    {"★".repeat(item.rating)}
                  </div>
                  <blockquote>&ldquo;{item.quote}&rdquo;</blockquote>
                  <div className="mkt-testimonial__author">
                    <strong>{item.name}</strong>
                    <span>{item.role}</span>
                  </div>
                </article>
              </MarketingReveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mkt-section mkt-section--muted" id="faq">
        <div className="mkt-section__inner">
          <MarketingReveal className="mkt-section__head mkt-section__head--center">
            <span className="mkt-kicker">FAQ</span>
            <h2>Common questions</h2>
          </MarketingReveal>
          <MarketingReveal>
            <FaqAccordion items={FAQ_ITEMS} />
          </MarketingReveal>
        </div>
      </section>

      <section className="mkt-cta">
        <MarketingReveal className="mkt-cta__inner">
          <h2>Ready to modernize commission operations?</h2>
          <p>
            See plans, orders, commissions, and payroll export on a walkthrough tailored
            to your regions and plan types.
          </p>
          <div className="mkt-cta__actions">
            <MarketingButton variant="primary" className="mkt-btn--large" onClick={showDemo}>
              Request demo
            </MarketingButton>
            <MarketingButton
              variant="ghost-light"
              className="mkt-btn--large"
              href="mailto:shivakumar@incentra.co.in?subject=Incentra%20consultation"
            >
              Book consultation
            </MarketingButton>
          </div>
        </MarketingReveal>
      </section>
    </>
  );
}

export default MarketingHome;
