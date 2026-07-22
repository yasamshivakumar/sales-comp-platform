import React, { createContext, useContext, useState, useEffect } from "react";

const ThemeContext = createContext();

function getInitialDarkMode() {
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme === "dark") return true;
  if (savedTheme === "light") return false;
  return false;
}

export function ThemeProvider({ children }) {
  const [isDarkMode, setIsDarkMode] = useState(getInitialDarkMode);

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      isDarkMode ? "dark" : "light"
    );
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");
  }, [isDarkMode]);

  const toggleTheme = () => {
    setIsDarkMode((prev) => !prev);
  };

  const theme = isDarkMode ? darkTheme : lightTheme;

  return (
    <ThemeContext.Provider value={{ isDarkMode, toggleTheme, theme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}

const darkTheme = {
  name: "dark",
  background: "#0a1b33",
  surface: "rgba(17, 28, 48, 0.72)",
  card: "rgba(15, 28, 48, 0.55)",
  border: "rgba(148, 163, 184, 0.18)",
  text: "#e2e8f0",
  textSecondary: "#cbd5e1",
  textTertiary: "#64748b",
  primary: "#1b96ff",
  primaryLight: "#5bb8ff",
  success: "#10b981",
  danger: "#ef4444",
  warning: "#f59e0b",
  overlay: "rgba(0, 0, 0, 0.7)",
};

const lightTheme = {
  name: "light",
  background: "#c5daf0",
  surface: "rgba(255, 255, 255, 0.72)",
  card: "rgba(255, 255, 255, 0.55)",
  border: "rgba(255, 255, 255, 0.55)",
  text: "#0f172a",
  textSecondary: "#475569",
  textTertiary: "#94a3b8",
  primary: "#0176d3",
  primaryLight: "#1b96ff",
  success: "#10b981",
  danger: "#ef4444",
  warning: "#f59e0b",
  overlay: "rgba(0, 0, 0, 0.5)",
};
