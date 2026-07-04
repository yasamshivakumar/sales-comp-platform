import { PRODUCT_AREAS } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import MarketingCta from "./MarketingCta";

function MarketingProductsIndex() {
  const { showProduct } = useMarketingNav();

  return (
    <>
      <section className="marketing-page-hero">
        <div className="marketing-page-hero__inner">
          <p className="marketing-kicker">Product</p>
          <h1>Modules shipped in Incentra</h1>
          <p className="marketing-page-hero__lead">
            These are the live areas of the application — not roadmap items. Select a module
            to see what it does today.
          </p>
        </div>
      </section>

      <section className="marketing-section marketing-section--wash">
        <div className="marketing-card-grid">
          {PRODUCT_AREAS.map((area) => (
            <button
              key={area.slug}
              type="button"
              className="marketing-card-link"
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

      <MarketingCta />
    </>
  );
}

export default MarketingProductsIndex;
