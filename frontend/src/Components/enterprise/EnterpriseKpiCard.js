import { Box, Typography } from "@mui/material";

export default function EnterpriseKpiCard({
  label,
  value,
  subtitle,
  icon: Icon,
  tone,
  active,
  onClick,
  trend,
}) {
  const interactive = typeof onClick === "function";
  const Comp = interactive ? "button" : "div";
  return (
    <Comp
      type={interactive ? "button" : undefined}
      className={`ent-kpi${tone ? ` ent-kpi--${tone}` : ""}${active ? " is-active" : ""}`}
      onClick={onClick}
    >
      {Icon ? (
        <span className="ent-kpi__icon" aria-hidden>
          <Icon fontSize="small" />
        </span>
      ) : null}
      <Typography component="span" className="ent-kpi__label">
        {label}
      </Typography>
      <Typography component="span" className="ent-kpi__value">
        {value}
      </Typography>
      {subtitle ? (
        <Typography component="span" className="ent-kpi__sub">
          {subtitle}
        </Typography>
      ) : null}
      {trend ? (
        <Box component="span" className="ent-kpi__trend">
          {trend}
        </Box>
      ) : null}
    </Comp>
  );
}

export function EnterpriseKpiGrid({ children, columns = "auto" }) {
  return (
    <div
      className="ent-kpi-grid"
      style={
        columns === "auto"
          ? undefined
          : { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }
      }
    >
      {children}
    </div>
  );
}
