import { PRODUCT_AREAS } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import MarketingCta from "./MarketingCta";

function MarketingProductsIndex() {
  const { showProduct } = useMarketingNav();

  return (
    <>
      <section className="marketing-page-hero marketing-page-hero--rich marketing-page-hero--catalog">
        <div className="marketing-page-hero__inner marketing-page-hero__inner--wide">
          <div className="marketing-hero-badges">
            <span className="marketing-hero-badge">5 live modules</span>
            <span className="marketing-hero-badge marketing-hero-badge--soft">Shipped today</span>
          </div>
          <p className="marketing-kicker">Product</p>
          <h1>Modules shipped in Incentra</h1>
          <p className="marketing-page-hero__lead">
            These are the live areas of the application — not roadmap items. Select a module
            to see what it does today.
          </p>
        </div>
      </section>

      <section className="marketing-section marketing-section--rich marketing-section--catalog">
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">Browse</p>
          <h2>Pick a module to explore</h2>
        </div>
        <div className="marketing-card-grid">
          {PRODUCT_AREAS.map((area) => (
            <button
              key={area.slug}
              type="button"
              className={`marketing-card-link marketing-card-link--rich marketing-card-link--${area.slug}`}
              onClick={() => showProduct(area.slug)}
            >
              <span className="marketing-card-link__label">{area.label}</span>
              <h3>{area.headline}</h3>
              <p>{area.summary}</p>
              <span className="marketing-card-link__meta">
                {area.items.length} capabilities
              </span>
              <span className="marketing-card-link__arrow">Learn more →</span>
            </button>
          ))}
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingProductsIndex;
