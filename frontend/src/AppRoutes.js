import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./Login";
import InviteAccept from "./InviteAccept";
import MarketingLayout from "./Marketing/MarketingLayout";
import Dashboard from "./Dashboard/Dashboard";

import AppLayout from "./Components/layout/AppLayout";
import CompensationPlans from "./CompensationPlans/CompensationPlans";
import CommissionRules from "./CommissionRules/CommissionRules";
import UserSetup from "./UserSetup/UserSetup";
import Orders from "./Orders/Orders";
import Commissions from "./Dashboard/Commissions";
import MyStatement from "./Dashboard/MyStatement";
import AuditLogs from "./Enterprise/AuditLogs";
import Payouts from "./Enterprise/Payouts";
import SalesByRegion from "./Dashboard/SalesByRegion";
import { getAuthToken } from "./api";

function PrivateRoute({ children }) {
  const token = getAuthToken();
  return token ? children : <Navigate to="/login" />;
}

function Layout({ children }) {
  return <AppLayout>{children}</AppLayout>;
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/signup" element={<Navigate to="/login" replace />} />
        <Route path="/" element={<MarketingLayout />} />
        <Route path="/product/*" element={<Navigate to="/" replace />} />
        <Route path="/teams/*" element={<Navigate to="/" replace />} />
        <Route path="/demo" element={<Navigate to="/" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/invite/:token" element={<InviteAccept />} />

        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <Layout>
                <Dashboard />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/sales-analysis"
          element={
            <PrivateRoute>
              <Layout>
                <SalesByRegion />
              </Layout>
            </PrivateRoute>
          }
        />
        <Route
          path="/sales-by-region"
          element={<Navigate to="/sales-analysis" replace />}
        />

        <Route
          path="/user-setup"
          element={
            <PrivateRoute>
              <Layout>
                <UserSetup />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/comp-plans"
          element={
            <PrivateRoute>
              <Layout>
                <CompensationPlans />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/commission-rules"
          element={
            <PrivateRoute>
              <Layout>
                <CommissionRules />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/orders"
          element={
            <PrivateRoute>
              <Layout>
                <Orders />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/statement"
          element={
            <PrivateRoute>
              <Layout>
                <MyStatement />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/commissions"
          element={
            <PrivateRoute>
              <Layout>
                <Commissions />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route
          path="/audit-logs"
          element={
            <PrivateRoute>
              <Layout>
                <AuditLogs />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route path="/territories" element={<Navigate to="/user-setup" replace />} />

        <Route
          path="/payouts"
          element={
            <PrivateRoute>
              <Layout>
                <Payouts />
              </Layout>
            </PrivateRoute>
          }
        />

        <Route path="/integrations" element={<Navigate to="/dashboard?integrations=1" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;
