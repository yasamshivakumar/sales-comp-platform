const STATUS_LABELS = {
  calculated: "Calculated",
  manager_approved: "Manager approved",
  approved: "Approved",
  paid: "Paid",
  open: "Open",
  resolved: "Resolved",
  rejected: "Rejected",
  draft: "Draft",
  no_commission: "No commission",
};

const COMPACT_LABELS = {
  calculated: "Calculated",
  manager_approved: "Mgr approved",
  approved: "Approved",
  paid: "Paid",
  open: "Open",
  resolved: "Resolved",
  rejected: "Rejected",
  draft: "Draft",
  no_commission: "No comm.",
};

function StatusPill({ status, label, compact = false }) {
  const key = status || "calculated";
  const text =
    label ||
    (compact ? COMPACT_LABELS[key] : STATUS_LABELS[key]) ||
    key.replace(/_/g, " ");
  return (
    <span
      className={`status-pill status-pill--${key}${compact ? " status-pill--compact" : ""}`}
    >
      {text}
    </span>
  );
}

export default StatusPill;
export { STATUS_LABELS };
