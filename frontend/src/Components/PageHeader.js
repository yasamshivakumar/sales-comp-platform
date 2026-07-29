import { PageShell } from "./enterprise";

/**
 * Legacy page header — delegates to the shared enterprise PageShell.
 */
function PageHeader({ title, subtitle, badge, children }) {
  return (
    <PageShell
      breadcrumbs={
        badge
          ? [{ label: "Incentra", to: "/dashboard" }, { label: badge }]
          : [{ label: "Incentra", to: "/dashboard" }, { label: title }]
      }
      title={title}
      subtitle={subtitle}
      secondaryActions={children || null}
      dense
    />
  );
}

export default PageHeader;
