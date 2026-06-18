import React from "react";
import ReactDOM from "react-dom/client";
import AppRoutes from "./AppRoutes";
import ErrorBoundary from "./ErrorBoundary";
import { ToastProvider } from "./Components/Toast";
import { ThemeProvider } from "./ThemeContext";
import MuiThemeProvider from "./Components/MuiThemeProvider";
import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/mui-bridge.css";
import "./styles/sidebar-nav.css";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <ErrorBoundary>
    <ThemeProvider>
      <MuiThemeProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </MuiThemeProvider>
    </ThemeProvider>
  </ErrorBoundary>
);
