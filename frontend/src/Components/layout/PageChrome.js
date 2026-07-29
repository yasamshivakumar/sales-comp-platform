import { Link } from "react-router-dom";
import { PageShell } from "../enterprise";
import "./pageChrome.css";

/**
 * Legacy page shell — delegates to the shared enterprise PageShell.
 */
function PageChrome({
  eyebrow,
  title,
  subtitle,
  primaryAction,
  search,
  filters,
  children,
  className = "",
}) {
  const breadcrumbs = eyebrow
    ? [{ label: "Incentra", to: "/dashboard" }, { label: eyebrow }]
    : undefined;

  const toolbar =
    search || filters ? (
      <>
        {search}
        {filters}
      </>
    ) : null;

  return (
    <PageShell
      breadcrumbs={breadcrumbs}
      title={title}
      subtitle={subtitle}
      primaryAction={primaryAction}
      toolbar={toolbar}
      className={className}
    >
      {children}
    </PageShell>
  );
}

export function ChromeButton({ to, onClick, children, variant = "secondary", disabled }) {
  const cls = `pg-btn${variant === "primary" ? " pg-btn--primary" : ""}`;
  if (to) {
    return (
      <Link className={cls} to={to}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" className={cls} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

export default PageChrome;
