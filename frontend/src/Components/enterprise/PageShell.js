import { Box, Stack, Typography } from "@mui/material";
import { OverflowActionsMenu } from "../Import";
import EnterpriseBreadcrumbs from "./EnterpriseBreadcrumbs";
import "./enterpriseShell.css";

/**
 * Standard enterprise page chrome:
 * Breadcrumb · Title · Subtitle · Primary · Secondary · Overflow
 */
export default function PageShell({
  breadcrumbs,
  eyebrow,
  title,
  subtitle,
  primaryAction,
  secondaryActions,
  overflowItems,
  toolbar,
  children,
  className = "",
  dense = false,
}) {
  const crumbs =
    breadcrumbs ||
    (eyebrow
      ? [{ label: "Incentra", to: "/dashboard" }, { label: eyebrow }]
      : null);

  return (
    <div className={`ent-page ${dense ? "ent-page--dense" : ""} ${className}`.trim()}>
      <header className="ent-page__header">
        <div className="ent-page__titles">
          {crumbs ? <EnterpriseBreadcrumbs items={crumbs} /> : null}
          <Typography component="h1" className="ent-page__title" variant="h1">
            {title}
          </Typography>
          {subtitle ? (
            <Typography className="ent-page__subtitle" variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          ) : null}
        </div>
        {(primaryAction || secondaryActions || (overflowItems && overflowItems.length > 0)) && (
          <div className="ent-page__actions">
            {secondaryActions ? (
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap className="ent-page__secondary">
                {secondaryActions}
              </Stack>
            ) : null}
            {primaryAction ? <div className="ent-page__primary">{primaryAction}</div> : null}
            {overflowItems?.length ? (
              <OverflowActionsMenu items={overflowItems} ariaLabel="Page actions" />
            ) : null}
          </div>
        )}
      </header>
      {toolbar ? <div className="ent-page__toolbar">{toolbar}</div> : null}
      <Box className="ent-page__body">{children}</Box>
    </div>
  );
}
