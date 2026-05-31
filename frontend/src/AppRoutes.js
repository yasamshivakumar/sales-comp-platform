import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./Login";
import Signup from "./Signup";
import App from "./App";

import Sidebar from "./Components/Sidebar";
import CompensationPlans from "./CompensationPlans/CompensationPlans";
import UserSetup from "./UserSetup/UserSetup";
import Orders from "./Orders/Orders";
import Commissions from "./Dashboard/Commissions";

function PrivateRoute({ children }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" />;
}

function Layout({ children }) {
  return (
    <div className="app-shell">
      <div className="app-shell__bg" aria-hidden="true" />
      <Sidebar />
      <main className="app-main">
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />

        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout>
                <App />
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
          path="/commissions"
          element={
            <PrivateRoute>
              <Layout>
                <Commissions />
              </Layout>
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;
