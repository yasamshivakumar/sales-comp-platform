import { useMarketingNav } from "../marketingNavContext";
import MarketingButton from "../components/MarketingButton";
import MarketingReveal from "../components/MarketingReveal";

function MarketingCta() {
  const { showDemo } = useMarketingNav();

  return (
    <section className="mkt-cta">
      <MarketingReveal className="mkt-cta__inner">
        <h2>See the live product on your workflow</h2>
        <p>Request a demo walkthrough of plans, orders, commissions, and payroll export.</p>
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
  );
}

export default MarketingCta;
