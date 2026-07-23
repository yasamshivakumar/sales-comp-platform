import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { useCallback, useEffect, useMemo, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import LoadingCenter from "../Components/LoadingCenter";
import { VersionBadge } from "./PlanVersionHistory";
import { displayVersionLabel, formatEffectiveRange } from "./compPlanUtils";

const TABS = [
  { to: "overview", label: "Overview" },
  { to: "versions", label: "Versions" },
  { to: "rates", label: "Rate Tables" },
  { to: "rules", label: "Rules" },
  { to: "quotas", label: "Quotas" },
  { to: "bonuses", label: "Bonuses" },
  { to: "accelerators", label: "Accelerators" },
  { to: "eligibility", label: "Eligibility" },
  { to: "participants", label: "Participants" },
  { to: "simulation", label: "Simulation" },
  { to: "approval", label: "Approval Workflow" },
  { to: "history", label: "Audit History" },
  { to: "settings", label: "Settings" },
];

function CompPlanWorkspace() {
  const { planId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { error } = useToast();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);

  const activeTab = useMemo(() => {
    const part = location.pathname.split("/").filter(Boolean).pop();
    return TABS.some((t) => t.to === part) ? part : "overview";
  }, [location.pathname]);

  const loadPlan = useCallback(async () => {
    if (!planId) return;
    setLoading(true);
    try {
      const res = await api.get(`compensation-plans/${planId}/`);
      setPlan(res.data);
    } catch (err) {
      error(getApiErrorMessage(err, "Failed to load plan"));
      navigate("/comp-plans");
    } finally {
      setLoading(false);
    }
  }, [planId, error, navigate]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  if (loading && !plan) {
    return <LoadingCenter minHeight={280} />;
  }
  if (!plan) return null;

  const cv = plan.current_version;
  const health = plan.health;

  return (
    <div className="cp-module cp-workspace">
      <div className="cp-workspace__top">
        <button type="button" className="cp-btn-ghost" onClick={() => navigate("/comp-plans")}>
          ← Operations Center
        </button>
        <div className="cp-workspace__title-block">
          <div className="cp-workspace__title-row">
            <h1 className="cp-workspace__title">{plan.plan_name}</h1>
            {health ? (
              <span className={`cp-health cp-health--${health.level}`}>
                <strong>{health.score}%</strong> {health.status}
              </span>
            ) : null}
          </div>
          <p className="cp-workspace__subtitle">
            {plan.role || "No role"}
            {plan.position_name ? ` · ${plan.position_name}` : ""}
            {plan.business_group ? ` · ${plan.business_group}` : ""}
            {" · "}
            {displayVersionLabel(plan)}{" "}
            {cv ? <VersionBadge status={cv.status} /> : null}
            {" · "}
            {cv
              ? formatEffectiveRange(cv.effective_from, cv.effective_to)
              : formatEffectiveRange(plan.effective_start_date, plan.effective_end_date)}
          </p>
        </div>
      </div>

      <div className="cp-workspace__body">
        <nav className="cp-workspace__nav" aria-label="Plan sections">
          <select
            className="cp-workspace__nav-select"
            aria-label="Plan section"
            value={activeTab}
            onChange={(e) => navigate(`/comp-plans/${planId}/${e.target.value}`)}
          >
            {TABS.map((tab) => (
              <option key={tab.to} value={tab.to}>
                {tab.label}
              </option>
            ))}
          </select>
          <ul className="cp-workspace__nav-list">
            {TABS.map((tab) => (
              <li key={tab.to}>
                <NavLink
                  to={`/comp-plans/${planId}/${tab.to}`}
                  className={({ isActive }) =>
                    `cp-workspace__nav-link${isActive ? " cp-workspace__nav-link--active" : ""}`
                  }
                >
                  {tab.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="cp-workspace__content">
          <Outlet context={{ plan, reloadPlan: loadPlan, setPlan }} />
        </div>
      </div>
    </div>
  );
}

export default CompPlanWorkspace;
