import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../api";
import ReportsAnalytics from "./ReportsAnalytics";
import "./dashboard.css";

function Dashboard() {
  const [profile, setProfile] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api
      .get("user-profile/")
      .then((res) => setProfile(res.data))
      .catch(() => setProfile(null))
      .finally(() => setLoaded(true));
  }, []);

  if (!loaded) {
    return <div className="unified-dashboard">Loading dashboard...</div>;
  }

  const canViewDashboard =
    Boolean(profile?.is_admin) || Boolean(profile?.is_finance) || Boolean(profile?.is_manager);

  if (!canViewDashboard) {
    return <Navigate to="/statement" replace />;
  }

  return (
    <div className="unified-dashboard">
      <ReportsAnalytics compact />
    </div>
  );
}

export default Dashboard;
