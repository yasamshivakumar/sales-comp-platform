import React from "react";
import ReactDOM from "react-dom/client";
import AppRoutes from "./AppRoutes";
import ErrorBoundary from "./ErrorBoundary";
import { ToastProvider } from "./Components/Toast";
import { ThemeProvider } from "./ThemeContext";
import "./styles.css";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <ErrorBoundary>
    <ThemeProvider>
      <ToastProvider>
        <AppRoutes />
      </ToastProvider>
    </ThemeProvider>
  </ErrorBoundary>
);