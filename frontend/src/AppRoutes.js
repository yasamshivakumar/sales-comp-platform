import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./Login";
import InviteAccept from "./InviteAccept";
import Dashboard from "./Dashboard/Dashboard";

import AppLayout from "./Components/layout/AppLayout";
import CompensationPlans from "./CompensationPlans/CompensationPlans";
import CommissionRules from "./CommissionRules/CommissionRules";
import UserSetup from "./UserSetup/UserSetup";
import Orders from "./Orders/Orders";
import Commissions from "./Dashboard/Commissions";
import MyStatement from "./Dashboard/MyStatement";
import AuditLogs from "./Enterprise/AuditLogs";
import Territories from "./Enterprise/Territories";
import Payouts from "./Enterprise/Payouts";
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
        <Route path="/login" element={<Login />} />
        <Route path="/invite/:token" element={<InviteAccept />} />

        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout>
                <Dashboard />
              </Layout>
            </PrivateRoute>
          }
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

        <Route
          path="/territories"
          element={
            <PrivateRoute>
              <Layout>
                <Territories />
              </Layout>
            </PrivateRoute>
          }
        />

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

        <Route path="/integrations" element={<Navigate to="/orders?tab=connect" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;
