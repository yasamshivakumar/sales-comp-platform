import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../api";
import CommandCenter from "./CommandCenter";
import LoadingCenter from "../Components/LoadingCenter";
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
    return (
      <div className="unified-dashboard unified-dashboard--loading">
        <LoadingCenter minHeight={240} size={24} />
      </div>
    );
  }

  const canViewDashboard =
    Boolean(profile?.is_admin) || Boolean(profile?.is_finance) || Boolean(profile?.is_manager);

  if (!canViewDashboard) {
    return <Navigate to="/statement" replace />;
  }

  return (
    <div className="unified-dashboard">
      <CommandCenter />
    </div>
  );
}

export default Dashboard;
