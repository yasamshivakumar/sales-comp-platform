import BookDemoForm from "../BookDemoForm";

function MarketingDemo() {
  return (
    <>
      <section className="marketing-page-hero marketing-page-hero--compact">
        <div className="marketing-page-hero__inner">
          <p className="marketing-kicker">Request demo</p>
          <h1>See Incentra on your workflow</h1>
          <p className="marketing-page-hero__lead">
            We will walk through plans, orders, commissions, and payroll export using your
            plan types and regions.
          </p>
        </div>
      </section>

      <section className="marketing-demo-section">
        <div className="marketing-demo-section__inner marketing-demo-section__inner--form-only">
          <BookDemoForm />
        </div>
      </section>
    </>
  );
}

export default MarketingDemo;
