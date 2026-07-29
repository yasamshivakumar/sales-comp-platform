import { Link } from "react-router-dom";
import "./pageChrome.css";

/**
 * Shared page shell: title, subtitle, primary action, optional search + filters.
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
  return (
    <div className={`pg-chrome ${className}`.trim()}>
      <header className="pg-chrome__header">
        <div className="pg-chrome__titles">
          {eyebrow ? <p className="pg-chrome__eyebrow">{eyebrow}</p> : null}
          <h1 className="pg-chrome__title">{title}</h1>
          {subtitle ? <p className="pg-chrome__subtitle">{subtitle}</p> : null}
        </div>
        {primaryAction ? <div className="pg-chrome__actions">{primaryAction}</div> : null}
      </header>
      {(search || filters) && (
        <div className="pg-chrome__toolbar">
          {search ? <div className="pg-chrome__search">{search}</div> : null}
          {filters ? <div className="pg-chrome__filters">{filters}</div> : null}
        </div>
      )}
      <div className="pg-chrome__body">{children}</div>
    </div>
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
