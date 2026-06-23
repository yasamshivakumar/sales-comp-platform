import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
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

const SOLUTIONS = [
  {
    title: "For sales operations",
    body: "Configure plans, rules, business groups, and territories without managing spreadsheets.",
  },
  {
    title: "For finance teams",
    body: "Approve commissions, export payroll-ready data, and track payout status from one workflow.",
  },
  {
    title: "For sales reps",
    body: "Give every rep a transparent incentive statement with calculation details and dispute support.",
  },
];

function MarketingSite() {
  const [demoForm, setDemoForm] = useState({
    name: "",
    email: "",
    company: "",
    phone: "",
    message: "",
  });
  const [demoStatus, setDemoStatus] = useState({ type: "", message: "" });
  const [demoSubmitting, setDemoSubmitting] = useState(false);

  const updateDemoForm = (field) => (event) => {
    setDemoForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const submitDemoRequest = async (event) => {
    event.preventDefault();
    setDemoStatus({ type: "", message: "" });
    setDemoSubmitting(true);
    try {
      await api.post("marketing/book-demo/", demoForm);
      setDemoStatus({
        type: "success",
        message: "Demo request sent. We will contact you shortly.",
      });
      setDemoForm({ name: "", email: "", company: "", phone: "", message: "" });
    } catch (err) {
      const fallbackEmail = err.response?.data?.contact_email || "shivakumar@incentra.co.in";
      const fallbackPhone = err.response?.data?.contact_phone || "8499087617";
      setDemoStatus({
        type: "error",
        message:
          err.response?.data?.error ||
          `Could not send demo request. Please email ${fallbackEmail} or call ${fallbackPhone}.`,
        email: fallbackEmail,
        phone: fallbackPhone,
      });
    } finally {
      setDemoSubmitting(false);
    }
  };

  return (
    <main className="marketing-site">
      <header className="marketing-nav">
        <Link to="/" className="marketing-brand" aria-label="Incentra home">
          <span className="marketing-brand__mark">I</span>
          <span>Incentra</span>
        </Link>
        <nav className="marketing-nav__links" aria-label="Marketing navigation">
          <a href="#home">Home</a>
          <a href="#features">Features</a>
          <a href="#solutions">Solutions</a>
          <a href="#about">About Us</a>
          <a href="#contact">Contact Us</a>
          <a href="#book-demo" className="marketing-nav__demo">
            Book Demo
          </a>
          <Link to="/login" className="marketing-nav__login">
            Login
          </Link>
        </nav>
      </header>

      <section className="marketing-hero" id="home">
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
              Contact us
            </a>
            <a href="#book-demo" className="marketing-button marketing-button--secondary">
              Book demo
            </a>
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

      <section className="marketing-section" id="solutions">
        <div className="marketing-section__head">
          <span className="marketing-kicker">Solutions</span>
          <h2>Built for every team involved in incentive payouts</h2>
          <p>
            Incentra connects sales operations, finance, and employees in one governed
            commission workspace.
          </p>
        </div>
        <div className="marketing-solution-grid">
          {SOLUTIONS.map((solution) => (
            <article className="marketing-solution-card" key={solution.title}>
              <h3>{solution.title}</h3>
              <p>{solution.body}</p>
            </article>
          ))}
        </div>
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

      <section className="marketing-about" id="about">
        <div>
          <span className="marketing-kicker">About Us</span>
          <h2>Incentra helps businesses make commissions transparent and reliable.</h2>
        </div>
        <p>
          We are building Incentra as an enterprise-ready sales compensation platform
          for companies that want accurate commission calculations, clean approval
          workflows, and better visibility for every employee.
        </p>
      </section>

      <section className="marketing-contact" id="contact">
        <div>
          <span className="marketing-kicker">Contact Us</span>
          <h2>Talk to Incentra</h2>
          <p>
            Reach out for product questions, onboarding help, or a walkthrough of how
            Incentra can support your sales compensation process.
          </p>
        </div>
        <div className="marketing-contact-card">
          <a href="mailto:shivakumar@incentra.co.in">
            <span>Email</span>
            <strong>shivakumar@incentra.co.in</strong>
          </a>
          <a href="tel:+918499087617">
            <span>Contact number</span>
            <strong>8499087617</strong>
          </a>
        </div>
      </section>

      <section className="marketing-cta" id="book-demo">
        <div>
          <span className="marketing-kicker">Book Demo</span>
          <h2>Launch a cleaner sales compensation process with Incentra.</h2>
          <p>
            Book a demo with the Incentra team and see how plans, rules, commissions,
            approvals, and employee statements work together.
          </p>
        </div>
        <form className="marketing-demo-form" onSubmit={submitDemoRequest}>
          <label>
            <span>Name *</span>
            <input
              value={demoForm.name}
              onChange={updateDemoForm("name")}
              placeholder="Your name"
              required
            />
          </label>
          <label>
            <span>Email *</span>
            <input
              type="email"
              value={demoForm.email}
              onChange={updateDemoForm("email")}
              placeholder="you@company.com"
              required
            />
          </label>
          <label>
            <span>Company</span>
            <input
              value={demoForm.company}
              onChange={updateDemoForm("company")}
              placeholder="Company name"
            />
          </label>
          <label>
            <span>Phone</span>
            <input
              value={demoForm.phone}
              onChange={updateDemoForm("phone")}
              placeholder="Phone number"
            />
          </label>
          <label className="marketing-demo-form__full">
            <span>Message</span>
            <textarea
              value={demoForm.message}
              onChange={updateDemoForm("message")}
              placeholder="Tell us about your commission process"
              rows={4}
            />
          </label>
          <button
            type="submit"
            className="marketing-button marketing-button--primary marketing-demo-form__submit"
            disabled={demoSubmitting}
          >
            {demoSubmitting ? "Sending..." : "Send demo request"}
          </button>
          {demoStatus.message && (
            <div className={`marketing-demo-form__status marketing-demo-form__status--${demoStatus.type}`}>
              <p>{demoStatus.message}</p>
              {demoStatus.type === "error" && (
                <div className="marketing-demo-form__fallback">
                  <a href={`mailto:${demoStatus.email}`}>{demoStatus.email}</a>
                  <a href={`tel:+91${demoStatus.phone}`}>{demoStatus.phone}</a>
                </div>
              )}
            </div>
          )}
        </form>
      </section>

      <footer className="marketing-footer">
        <span>© {new Date().getFullYear()} Incentra</span>
        <span>shivakumar@incentra.co.in · 8499087617</span>
      </footer>
    </main>
  );
}

export default MarketingSite;
