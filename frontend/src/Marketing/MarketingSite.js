import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import "./marketing.css";

const FEATURES = [
  {
    title: "Reliable incentive management",
    body: "Move away from manual tracking and give your teams a cleaner way to manage sales incentives.",
  },
  {
    title: "Clear team visibility",
    body: "Help leaders, finance teams, and employees understand performance and earnings with confidence.",
  },
  {
    title: "Designed for growing companies",
    body: "Support multiple teams and business units with a structured, secure compensation process.",
  },
  {
    title: "Employee transparency",
    body: "Give employees a simple place to review incentive information and reduce back-and-forth questions.",
  },
  {
    title: "Finance-ready process",
    body: "Keep incentive reviews, approvals, and payout preparation organized from one place.",
  },
  {
    title: "Built with trust in mind",
    body: "Keep company data protected and make important compensation activity easier to review.",
  },
];

const SOLUTIONS = [
  {
    title: "Sales teams",
    body: "Keep compensation clear so sales teams can focus on revenue instead of incentive confusion.",
  },
  {
    title: "Finance teams",
    body: "Review incentive numbers with better structure before payout preparation.",
  },
  {
    title: "Business leaders",
    body: "Understand incentive spend, team performance, and compensation outcomes at a higher level.",
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
          <span className="marketing-kicker">Incentive compensation platform</span>
          <h1>Make sales incentives clear, accurate, and easier to manage.</h1>
          <p>
            Incentra helps companies manage incentive compensation with better visibility,
            cleaner workflows, and a transparent experience for teams.
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
            <span>For growing teams</span>
            <span>Simple to use</span>
            <span>Built for trust</span>
          </div>
        </div>

        <div className="marketing-hero-panel" aria-label="Incentra overview">
          <span>Incentra</span>
          <h2>Modern incentive operations for sales-led companies.</h2>
          <p>
            A focused platform for companies that want incentive compensation to be
            easier to understand, manage, and scale.
          </p>
        </div>
      </section>

      <section className="marketing-section" id="features">
        <div className="marketing-section__head">
          <span className="marketing-kicker">Features</span>
          <h2>A simpler way to manage sales incentives</h2>
          <p>
            Incentra brings structure, clarity, and control to incentive compensation
            without making teams depend on scattered spreadsheets.
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

      <section className="marketing-section" id="solutions">
        <div className="marketing-section__head">
          <span className="marketing-kicker">Solutions</span>
          <h2>Built for teams that care about clean compensation</h2>
          <p>
            Incentra supports the people involved in sales incentives, from leadership
            to finance to employees who need clarity.
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

      <section className="marketing-about" id="about">
        <div>
          <span className="marketing-kicker">About Us</span>
          <h2>Incentra helps businesses make commissions transparent and reliable.</h2>
        </div>
        <p>
          We are building Incentra for companies that want a more professional way to
          manage sales incentives, improve team trust, and reduce manual compensation
          work as the business grows.
        </p>
      </section>

      <section className="marketing-contact" id="contact">
        <div>
          <span className="marketing-kicker">Contact Us</span>
          <h2>Talk to Incentra</h2>
          <p>
            Reach out for product questions, onboarding help, or a walkthrough of how
            Incentra can support your compensation process.
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
            Book a demo with the Incentra team and see how a cleaner incentive
            management experience can support your business.
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
