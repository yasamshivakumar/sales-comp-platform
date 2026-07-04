/** Platform areas that map to shipped Incentra modules (verified in product). */
export const PRODUCT_AREAS = [
  {
    id: "design",
    slug: "plans",
    label: "Plans",
    headline: "Compensation plan design",
    summary: "Monthly plans with effective dates, scoped by role, position, and business group.",
    items: [
      { name: "Rate, flat & lookup plans", description: "Tiered rates, flat amounts, and SC lookup tables by product, service, or distribution." },
      { name: "Commission rules", description: "Conditional rules and overrides on top of base plan logic." },
      { name: "Business groups", description: "India, USA, Australia, and Europe with currency-aligned reporting." },
    ],
  },
  {
    id: "manage",
    slug: "participants",
    label: "Participants & orders",
    headline: "Participants, orders, and territories",
    summary: "Onboard reps, import deals, and keep attribution in one tenant-scoped workspace.",
    items: [
      { name: "User setup & invites", description: "Admin, finance, manager, and rep roles with invite-based employee login." },
      { name: "Order queue", description: "Create or import orders, mark Success, and trigger monthly commission calculation." },
      { name: "CSV & bulk import", description: "Upload order and employee files; large imports run asynchronously." },
      { name: "Territories", description: "Assign territories to participants and orders." },
    ],
  },
  {
    id: "integrations",
    slug: "crm-sync",
    label: "CRM sync",
    headline: "CRM order sync",
    summary: "Pull closed deals from your CRM into the order queue with deduplication.",
    items: [
      { name: "Salesforce", description: "Sync deals into orders mapped to employees in your org." },
      { name: "HubSpot", description: "Incremental sync and webhook support for deal updates." },
      { name: "Zoho", description: "Import CRM deals with owner-to-employee mapping." },
    ],
  },
  {
    id: "incent",
    slug: "commissions",
    label: "Commissions",
    headline: "Commission calculation & payout",
    summary: "Monthly aggregation, hierarchy splits, approvals, and payroll export.",
    items: [
      { name: "Monthly calculation", description: "Aggregate successful orders per employee per month into one commission row." },
      { name: "Hierarchy splits", description: "Managers receive the remainder when reps keep a configured split percentage." },
      { name: "Approvals", description: "Calculated → manager approved → finance approved → paid status tracking." },
      { name: "Payroll CSV export", description: "Export approved commissions for finance and payroll processing." },
      { name: "Disputes & statements", description: "Reps view incentive details and raise disputes; finance resolves them." },
    ],
  },
  {
    id: "analytics",
    slug: "dashboard",
    label: "Dashboard",
    headline: "Dashboard & reporting",
    summary: "Commission and sales analytics with filters your teams use today.",
    items: [
      { name: "Commission & sales KPIs", description: "Totals by period, currency, and business group." },
      { name: "Leaderboard & earnings", description: "Rank reps and drill into earnings by employee." },
      { name: "Quota attainment", description: "Compare closed sales to personal targets on the dashboard." },
      { name: "Audit logs", description: "Review sensitive actions across the organization." },
    ],
  },
];

export const SOLUTIONS_BY_FUNCTION = [
  {
    id: "finance",
    slug: "finance",
    label: "Finance",
    title: "Approve commissions and export payroll",
    body: "Filter commissions by period and status, approve calculated rows in bulk, and download a payroll CSV. Commission amounts tie to successful orders and monthly aggregation rules.",
    bullets: ["Bulk approve calculated commissions", "Payroll CSV export", "Audit logs", "Multi-currency totals by business group"],
  },
  {
    id: "compensation",
    slug: "compensation",
    label: "Compensation",
    title: "Build and maintain plan logic",
    body: "Create monthly compensation plans with rate, flat, or lookup tables. Set effective dates, roles, positions, and business groups without spreadsheet formulas.",
    bullets: ["Rate / flat / lookup plans", "Commission rules", "Monthly effective periods", "Plan copy and versioning in-app"],
  },
  {
    id: "operations",
    slug: "revops",
    label: "RevOps",
    title: "Get CRM deals into Incentra",
    body: "Connect Salesforce, HubSpot, or Zoho to sync deals as orders. Map CRM owners to employees and recalculate when new deals arrive in the same month.",
    bullets: ["CRM Connect (3 providers)", "Order deduplication by CRM id", "CSV fallback import", "Order success workflow"],
  },
  {
    id: "sales",
    slug: "sales",
    label: "Sales",
    title: "Transparent earnings for reps",
    body: "Sales reps sign in to view incentive details, monthly statements, and commission status. They can raise a dispute when something needs review.",
    bullets: ["Incentive details by period", "My statement view", "Dispute workflow", "Role-scoped data access"],
  },
];

export function getProductArea(slug) {
  return PRODUCT_AREAS.find((area) => area.slug === slug);
}

export function getTeamSolution(slug) {
  return SOLUTIONS_BY_FUNCTION.find((team) => team.slug === slug);
}
