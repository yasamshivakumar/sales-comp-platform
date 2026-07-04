import { useMarketingNav } from "../marketingNavContext";

function MarketingCta() {
  const { showDemo } = useMarketingNav();

  return (
    <section className="marketing-cta-band">
      <div className="marketing-cta-band__inner">
        <h2>See the live product on your workflow</h2>
        <p>Request a demo walkthrough of plans, orders, commissions, and payroll export.</p>
        <button type="button" className="marketing-btn marketing-btn--primary marketing-btn--large" onClick={showDemo}>
          Book a demo
        </button>
      </div>
    </section>
  );
}

export default MarketingCta;
