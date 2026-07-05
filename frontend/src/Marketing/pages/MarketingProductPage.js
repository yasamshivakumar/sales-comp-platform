import { getProductArea, PRODUCT_AREAS } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import { ModulePreviewVisual } from "../MarketingVisuals";
import MarketingCta from "./MarketingCta";

function MarketingProductPage({ slug }) {
  const { showProduct } = useMarketingNav();
  const area = getProductArea(slug);

  if (!area) {
    return null;
  }

  const otherAreas = PRODUCT_AREAS.filter((item) => item.slug !== slug);

  return (
    <>
      <section className={`marketing-page-hero marketing-page-hero--rich marketing-page-hero--module-${slug}`}>
        <div className="marketing-page-hero__inner marketing-page-hero__inner--split">
          <div className="marketing-page-hero__copy-block">
            <p className="marketing-kicker">Product · {area.label}</p>
            <h1>{area.headline}</h1>
            <p className="marketing-page-hero__lead">{area.summary}</p>
          </div>
          <ModulePreviewVisual slug={slug} label={area.label} />
        </div>
      </section>

      <section className={`marketing-pillar marketing-pillar--rich marketing-pillar--module-${slug}`}>
        <div className="marketing-pillar__inner marketing-pillar__inner--single">
          <div className="marketing-pillar__head marketing-pillar__head--center">
            <p className="marketing-kicker">Capabilities</p>
            <h2>What you can do in {area.label}</h2>
            <p>Capabilities available in Incentra today.</p>
          </div>
          <div className="marketing-feature-grid">
            {area.items.map((item) => (
              <article className="marketing-feature-card" key={item.name}>
                <h3>{item.name}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={`marketing-section marketing-section--rich marketing-section--module-${slug}`}>
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">More modules</p>
          <h2>Explore other product areas</h2>
          <p className="marketing-section__sub">
            Each module connects in the same tenant — plans, orders, commissions, and payroll.
          </p>
        </div>
        <div className="marketing-card-grid marketing-card-grid--compact">
          {otherAreas.map((item) => (
            <button
              key={item.slug}
              type="button"
              className={`marketing-card-link marketing-card-link--solid marketing-card-link--rich marketing-card-link--${item.slug}`}
              onClick={() => showProduct(item.slug)}
            >
              <span className="marketing-card-link__label">{item.label}</span>
              <h3>{item.headline}</h3>
              <span className="marketing-card-link__arrow">View details</span>
            </button>
          ))}
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingProductPage;
