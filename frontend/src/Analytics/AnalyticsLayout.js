import { useEffect, useState } from "react";
import { NavLink, Outlet, Navigate, useLocation } from "react-router-dom";
import api from "../api";
import "./analytics.css";

const ALL_TABS = [
  { to: "/analytics/reports", label: "Reports", roles: "all" },
  { to: "/analytics/saved", label: "Saved Reports", roles: "all" },
  { to: "/analytics/builder", label: "Report Builder", roles: "builder" },
  { to: "/analytics/schedules", label: "Scheduled Reports", roles: "builder" },
];

function AnalyticsLayout() {
  const location = useLocation();
  const [profileReady, setProfileReady] = useState(false);
  const [canBuild, setCanBuild] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get("user-profile/")
      .then((res) => {
        if (cancelled) return;
        const p = res.data || {};
        setCanBuild(Boolean(p.is_admin || p.is_finance || p.is_manager));
      })
      .catch(() => {
        if (!cancelled) setCanBuild(false);
      })
      .finally(() => {
        if (!cancelled) setProfileReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (location.pathname === "/analytics" || location.pathname === "/analytics/") {
    return <Navigate to="/analytics/reports" replace />;
  }

  const restricted =
    location.pathname.startsWith("/analytics/builder") ||
    location.pathname.startsWith("/analytics/schedules");

  if (profileReady && !canBuild && restricted) {
    return <Navigate to="/analytics/reports" replace />;
  }

  const tabs = ALL_TABS.filter((t) => t.roles === "all" || canBuild);

  return (
    <div className="an-root">
      <header className="an-header">
        <div>
          <p className="an-eyebrow">Reporting center</p>
          <h1>Analytics</h1>
          <p className="an-sub">
            Build, save, schedule, and export custom reports — separate from the executive Dashboard.
          </p>
        </div>
      </header>
      <nav className="an-tabs" aria-label="Analytics sections">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.to === "/analytics/reports"}
            className={({ isActive }) => {
              if (t.to === "/analytics/reports") {
                const onLibrary =
                  location.pathname === "/analytics/reports" ||
                  /^\/analytics\/reports\/\d+/.test(location.pathname);
                return onLibrary ? "an-tab an-tab--active" : "an-tab";
              }
              return isActive ? "an-tab an-tab--active" : "an-tab";
            }}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}

export default AnalyticsLayout;
