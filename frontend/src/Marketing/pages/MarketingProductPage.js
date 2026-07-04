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
      <section className="marketing-page-hero">
        <div className="marketing-page-hero__inner marketing-page-hero__inner--split">
          <div>
            <p className="marketing-kicker">Product · {area.label}</p>
            <h1>{area.headline}</h1>
            <p className="marketing-page-hero__lead">{area.summary}</p>
          </div>
          <ModulePreviewVisual slug={slug} label={area.label} />
        </div>
      </section>

      <section className="marketing-pillar">
        <div className="marketing-pillar__inner marketing-pillar__inner--single">
          <div className="marketing-pillar__grid marketing-pillar__grid--wide">
            {area.items.map((item) => (
              <article className="marketing-pillar-card" key={item.name}>
                <h3>{item.name}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-section marketing-section--wash">
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">More modules</p>
          <h2>Explore other product areas</h2>
        </div>
        <div className="marketing-card-grid marketing-card-grid--compact">
          {otherAreas.map((item) => (
            <button
              key={item.slug}
              type="button"
              className="marketing-card-link"
              onClick={() => showProduct(item.slug)}
            >
              <span className="marketing-card-link__label">{item.label}</span>
              <h3>{item.headline}</h3>
              <span className="marketing-card-link__arrow">View module →</span>
            </button>
          ))}
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingProductPage;
