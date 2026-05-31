import React, { createContext, useContext, useState, useEffect } from "react";

const ThemeContext = createContext();

export function ThemeProvider({ children }) {
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Load theme preference from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
      setIsDarkMode(savedTheme === "dark");
    }
    document.documentElement.setAttribute(
      "data-theme",
      savedTheme === "light" ? "light" : "dark"
    );
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      isDarkMode ? "dark" : "light"
    );
  }, [isDarkMode]);

  const toggleTheme = () => {
    setIsDarkMode((prev) => {
      const newMode = !prev;
      localStorage.setItem("theme", newMode ? "dark" : "light");
      return newMode;
    });
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

// Dark Theme (Current - Blue/Gray)
const darkTheme = {
  name: "dark",
  background: "#020617",
  surface: "#0f172a",
  card: "rgba(20, 20, 30, 0.9)",
  border: "#1e293b",
  text: "#e2e8f0",
  textSecondary: "#cbd5e1",
  textTertiary: "#64748b",
  primary: "#2563eb",
  primaryLight: "#3b82f6",
  success: "#10b981",
  danger: "#ef4444",
  warning: "#f59e0b",
  overlay: "rgba(0, 0, 0, 0.7)",
};

// Light Theme (New - Clean & Bright)
const lightTheme = {
  name: "light",
  background: "#f8fafc",
  surface: "#f1f5f9",
  card: "#ffffff",
  border: "#e2e8f0",
  text: "#0f172a",
  textSecondary: "#475569",
  textTertiary: "#94a3b8",
  primary: "#2563eb",
  primaryLight: "#3b82f6",
  success: "#10b981",
  danger: "#ef4444",
  warning: "#f59e0b",
  overlay: "rgba(0, 0, 0, 0.5)",
};
