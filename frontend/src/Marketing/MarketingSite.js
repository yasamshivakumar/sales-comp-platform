import { Link } from "react-router-dom";
import "./marketing.css";

const FEATURES = [
  {
    title: "Monthly commission automation",
    body: "Aggregate orders, apply plan tiers, and generate clean payout-ready commission summaries.",
  },
  {
    title: "Enterprise tenant isolation",
    body: "Keep each company's people, orders, plans, commissions, disputes, and audit data separated.",
  },
  {
    title: "Role-based workflows",
    body: "Give sales reps, managers, finance, and admins the right screens for approval and payout work.",
  },
  {
    title: "Employee incentive portal",
    body: "Let reps review statements, understand calculations, and raise disputes from one place.",
  },
  {
    title: "Flexible comp plans",
    body: "Model rate, flat, lookup, bonus, and override rules across currencies and business groups.",
  },
  {
    title: "Audit-ready operations",
    body: "Track approvals, payouts, disputes, imports, integrations, and sensitive admin actions.",
  },
];

const STEPS = [
  "Upload or sync orders",
  "Match active compensation plans",
  "Calculate incentives by employee period",
  "Approve, export, and pay",
];

function MarketingSite() {
  return (
    <main className="marketing-site">
      <header className="marketing-nav">
        <Link to="/" className="marketing-brand" aria-label="Incentra home">
          <span className="marketing-brand__mark">I</span>
          <span>Incentra</span>
        </Link>
        <nav className="marketing-nav__links" aria-label="Marketing navigation">
          <a href="#features">Features</a>
          <a href="#workflow">Workflow</a>
          <a href="#security">Security</a>
          <Link to="/login" className="marketing-nav__login">
            Login
          </Link>
        </nav>
      </header>

      <section className="marketing-hero">
        <div className="marketing-hero__copy">
          <span className="marketing-kicker">Enterprise incentive compensation</span>
          <h1>Calculate commissions with confidence, not spreadsheets.</h1>
          <p>
            Incentra helps sales operations and finance teams design compensation plans,
            calculate monthly incentives, approve payouts, and give every rep a clear
            statement of earnings.
          </p>
          <div className="marketing-hero__actions">
            <a href="#contact" className="marketing-button marketing-button--primary">
              Book a demo
            </a>
            <Link to="/login" className="marketing-button marketing-button--secondary">
              Customer login
            </Link>
          </div>
          <div className="marketing-proof">
            <span>Multi-currency</span>
            <span>Tenant isolated</span>
            <span>Approval workflows</span>
          </div>
        </div>

        <div className="marketing-product-card" aria-label="Product preview">
          <div className="marketing-product-card__top">
            <span>June payout run</span>
            <strong>Ready for finance</strong>
          </div>
          <div className="marketing-metric-grid">
            <div>
              <span>Total sales</span>
              <strong>$1.28M</strong>
            </div>
            <div>
              <span>Commission</span>
              <strong>$84.6K</strong>
            </div>
            <div>
              <span>Reps paid</span>
              <strong>42</strong>
            </div>
            <div>
              <span>Disputes</span>
              <strong>2 open</strong>
            </div>
          </div>
          <div className="marketing-bars">
            <span style={{ "--bar": "82%" }}>North America</span>
            <span style={{ "--bar": "64%" }}>India</span>
            <span style={{ "--bar": "48%" }}>Australia</span>
          </div>
        </div>
      </section>

      <section className="marketing-section" id="features">
        <div className="marketing-section__head">
          <span className="marketing-kicker">Platform</span>
          <h2>Everything needed to run incentive compensation</h2>
          <p>
            Replace manual worksheets with a governed commission workflow that connects
            orders, plans, approvals, disputes, and payouts.
          </p>
        </div>
        <div className="marketing-feature-grid">
          {FEATURES.map((feature) => (
            <article className="marketing-feature-card" key={feature.title}>
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="marketing-workflow" id="workflow">
        <div>
          <span className="marketing-kicker">Workflow</span>
          <h2>From successful orders to approved payouts</h2>
          <p>
            Incentra calculates commissions after summing successful orders by employee,
            month, and currency, so tiers are chosen from the true period performance.
          </p>
        </div>
        <ol className="marketing-step-list">
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="marketing-security" id="security">
        <div>
          <span className="marketing-kicker">Trust</span>
          <h2>Built for companies, teams, and controlled access</h2>
        </div>
        <div className="marketing-security__grid">
          <p>Company-scoped data access for enterprise tenant isolation.</p>
          <p>Role-based navigation for reps, managers, finance, and admins.</p>
          <p>Audit logs for approvals, payouts, disputes, and user operations.</p>
        </div>
      </section>

      <section className="marketing-cta" id="contact">
        <div>
          <span className="marketing-kicker">Ready to modernize commissions?</span>
          <h2>Launch a cleaner sales compensation process with Incentra.</h2>
          <p>
            Use this page as your public website now, then connect a demo/contact form
            when your sales process is ready.
          </p>
        </div>
        <Link to="/login" className="marketing-button marketing-button--primary">
          Go to app
        </Link>
      </section>

      <footer className="marketing-footer">
        <span>© {new Date().getFullYear()} Incentra</span>
        <span>Sales compensation, commissions, and payouts</span>
      </footer>
    </main>
  );
}

export default MarketingSite;
