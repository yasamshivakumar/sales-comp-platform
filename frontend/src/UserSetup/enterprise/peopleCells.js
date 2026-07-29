import { Avatar, Chip, Tooltip } from "@mui/material";

function initials(name, email) {
  const source = (name || email || "?").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase() || "?";
}

const AVATAR_COLORS = [
  "#0176d3",
  "#0b827c",
  "#8b5cf6",
  "#c2410c",
  "#0369a1",
  "#4f46e5",
];

function colorFor(seed) {
  const s = String(seed || "");
  let hash = 0;
  for (let i = 0; i < s.length; i += 1) hash = (hash + s.charCodeAt(i) * 17) % AVATAR_COLORS.length;
  return AVATAR_COLORS[hash];
}

export function EmployeeAvatar({ person, size = 40 }) {
  const name = person?.display_name || person?.name || "";
  const email = person?.email || "";
  return (
    <Avatar
      className="pe-ent-avatar"
      sx={{
        width: size,
        height: size,
        fontSize: size > 36 ? 14 : 12,
        fontWeight: 700,
        bgcolor: colorFor(person?.id || email || name),
      }}
      alt={name || email}
    >
      {initials(name, email)}
    </Avatar>
  );
}

export function EmptyValue({ label = "Not assigned" }) {
  return <span className="pe-empty-val">{label}</span>;
}

export function RoleChip({ role }) {
  if (!role) return <EmptyValue label="No role" />;
  const tone =
    /admin/i.test(role)
      ? "admin"
      : /manager/i.test(role)
        ? "manager"
        : /finance/i.test(role)
          ? "finance"
          : "sales";
  return <Chip size="small" label={role} className={`pe-chip pe-chip--role-${tone}`} />;
}

export function StatusChip({ code, label }) {
  const text = label || code || "Unknown";
  const tone =
    code === "active" || code === "plan_assigned"
      ? "active"
      : code === "pending_activation" || code === "invited"
        ? "pending"
        : code === "suspended" || code === "inactive"
          ? "inactive"
          : "neutral";
  return (
    <Chip
      size="small"
      className={`pe-chip pe-chip--status-${tone}`}
      label={
        <span>
          <span className={`pe-status-dot pe-status-dot--${tone}`} aria-hidden />
          {text}
        </span>
      }
    />
  );
}

export function CompensationPlanChip({ plan }) {
  if (!plan) return <EmptyValue label="No plan" />;
  return (
    <Chip
      size="small"
      label={plan}
      className="pe-chip pe-chip--plan"
      title={plan}
    />
  );
}

export function SoftChip({ value, empty = "Not assigned" }) {
  if (!value) return <EmptyValue label={empty} />;
  return <Chip size="small" label={value} className="pe-chip pe-chip--soft" variant="outlined" />;
}

export function formatRelativeTime(value) {
  if (!value) return "Never";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 14) return `${days} days ago`;
  return d.toLocaleDateString();
}

export function RelativeTime({ value }) {
  const label = formatRelativeTime(value);
  if (!value) return <EmptyValue label="Never" />;
  const full = new Date(value);
  const title = Number.isNaN(full.getTime()) ? String(value) : full.toLocaleString();
  return (
    <Tooltip title={title}>
      <span className="pe-relative-time">{label}</span>
    </Tooltip>
  );
}

export function EmployeeIdentityCell({ person, onOpen }) {
  const name = person.display_name || person.name || "Unnamed";
  return (
    <button
      type="button"
      className="pe-identity"
      onClick={(e) => {
        e.stopPropagation();
        onOpen?.(person);
      }}
    >
      <EmployeeAvatar person={person} size={40} />
      <span className="pe-identity__text">
        <span className="pe-identity__name">{name}</span>
        <span className="pe-identity__id">{person.employee_id || "No employee ID"}</span>
        <span className="pe-identity__email">{person.email || "No email"}</span>
      </span>
    </button>
  );
}
