import ReportsAnalytics from "./ReportsAnalytics";
import "./dashboard.css";

function Dashboard() {
  return (
    <div className="unified-dashboard">
      <ReportsAnalytics compact />
    </div>
  );
}

export default Dashboard;
