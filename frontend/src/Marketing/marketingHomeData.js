/** Home page marketing content — maps to live Incentra capabilities */

export const TRUST_METRICS = [
  { value: "99.9%", label: "Target platform uptime" },
  { value: "Multi-tenant", label: "Isolated org data" },
  { value: "3 CRMs", label: "Salesforce · HubSpot · Zoho" },
  { value: "Days", label: "To first commission run" },
];

export const TRUST_LOGOS = [
  "Finance",
  "Compensation",
  "RevOps",
  "Sales",
  "Operations",
  "Leadership",
];

export const HOME_BENEFITS = [
  {
    id: "automation",
    title: "Automation",
    description: "Monthly commission runs, hierarchy splits, and payroll export without spreadsheet macros.",
  },
  {
    id: "accuracy",
    title: "Accuracy",
    description: "Plans, rules, and order data in one system of record — auditable from deal to payout.",
  },
  {
    id: "scalability",
    title: "Scalability",
    description: "Multi-tenant architecture with role-based access for admins, finance, managers, and reps.",
  },
  {
    id: "compliance",
    title: "Compliance",
    description: "Audit logs, approval workflows, and dispute resolution built into the platform.",
  },
  {
    id: "visibility",
    title: "Visibility",
    description: "Dashboards, statements, and earnings views for finance and sales leadership.",
  },
  {
    id: "security",
    title: "Enterprise security",
    description: "Organization-scoped data, invite-based access, and production operations runbooks.",
  },
];

export const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Connect data",
    description: "Sync CRM deals or import orders. Map participants, territories, and business groups.",
  },
  {
    step: "02",
    title: "Configure plans",
    description: "Set rate, flat, and lookup plans with commission rules and monthly effective dates.",
  },
  {
    step: "03",
    title: "Automate calculations",
    description: "Run monthly aggregation on successful orders with manager hierarchy splits.",
  },
  {
    step: "04",
    title: "Generate payouts",
    description: "Finance approves commissions and exports payroll CSV with full status tracking.",
  },
];

export const SCREENSHOT_SECTIONS = [
  {
    id: "plans",
    kicker: "Compensation plans",
    title: "Design plans finance and RevOps can trust",
    description:
      "Build monthly plans with tiered rates, flat amounts, and lookup tables. Layer commission rules and business groups for India, USA, Australia, and Europe.",
    align: "left",
  },
  {
    id: "commissions",
    kicker: "Commission operations",
    title: "From booked orders to approved payouts",
    description:
      "Queue orders, calculate monthly commissions, route approvals, and export payroll — with disputes and statements for reps.",
    align: "right",
  },
];

export const TESTIMONIALS = [
  {
    quote:
      "We replaced spreadsheet commission cycles with a single workflow. Finance finally has one place to approve and export.",
    name: "VP Finance",
    role: "Enterprise SaaS",
    rating: 5,
  },
  {
    quote:
      "RevOps connected our CRM and cut manual order uploads. The team trusts the numbers because the logic lives in the product.",
    name: "Director, Revenue Operations",
    role: "B2B software",
    rating: 5,
  },
  {
    quote:
      "Compensation admins can update plans and effective dates without engineering. That alone saved us weeks every quarter.",
    name: "Head of Compensation",
    role: "Global sales org",
    rating: 5,
  },
];

export const FAQ_ITEMS = [
  {
    question: "What does Incentra replace?",
    answer:
      "Spreadsheet-based commission tracking, manual payroll prep, and disconnected CRM-to-payout workflows. Incentra is the system of record for plans, orders, commissions, and export.",
  },
  {
    question: "Which CRMs do you support?",
    answer:
      "Salesforce, HubSpot, and Zoho connectors sync deals into your order queue with deduplication and owner mapping.",
  },
  {
    question: "How long does implementation take?",
    answer:
      "Most teams run a first commission period within days: participant setup, plan configuration, order ingestion, and a monthly calculation cycle.",
  },
  {
    question: "Is data isolated per company?",
    answer:
      "Yes. Incentra is multi-tenant SaaS — each organization’s data is scoped by tenant with role-based access for admin, finance, manager, and rep users.",
  },
  {
    question: "Can reps see their earnings?",
    answer:
      "Sales reps sign in to view incentive details, monthly statements, and commission status. They can raise disputes when something needs review.",
  },
  {
    question: "How do I see the product?",
    answer:
      "Request a demo walkthrough. We show plans, orders, commissions, and payroll export on your plan types and regions.",
  },
];
