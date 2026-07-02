import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import HubOutlinedIcon from "@mui/icons-material/HubOutlined";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import api from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";
import Integrations from "../Enterprise/Integrations";
import ReportsAnalytics from "./ReportsAnalytics";
import "./dashboard.css";

const TABS = [
  { id: "overview", label: "Overview", Icon: InsightsOutlinedIcon },
  { id: "connect", label: "Connect", Icon: HubOutlinedIcon },
];

function Dashboard() {
  const { success } = useToast();
  const [searchParams] = useSearchParams();
  const [profile, setProfile] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    api
      .get("user-profile/")
      .then((res) => setProfile(res.data))
      .catch(() => setProfile(null))
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab && TABS.some((item) => item.id === tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  if (!loaded) {
    return <div className="unified-dashboard">Loading dashboard...</div>;
  }

  const canViewDashboard =
    Boolean(profile?.is_admin) || Boolean(profile?.is_finance) || Boolean(profile?.is_manager);

  if (!canViewDashboard) {
    return <Navigate to="/statement" replace />;
  }

  const handleOrdersSynced = (data) => {
    const count = data?.result?.success ?? 0;
    if (count > 0) {
      success(`Synced ${count} order(s) from CRM — check Orders for results.`);
    }
  };

  return (
    <div className="unified-dashboard">
      <PageHeader
        badge="Workspace"
        title="Dashboard"
        subtitle="Performance overview and CRM connections for your organization."
      />

      <div className="dashboard-toolbar">
        <div className="dashboard-tabs" role="tablist" aria-label="Dashboard sections">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`dashboard-tab${activeTab === tab.id ? " dashboard-tab--active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <tab.Icon className="dashboard-tab__icon" fontSize="small" aria-hidden="true" />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="dashboard-workspace">
        {activeTab === "overview" && <ReportsAnalytics compact />}
        {activeTab === "connect" && (
          <div className="dashboard-connect">
            <Integrations embedded inline onOrdersSynced={handleOrdersSynced} />
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
