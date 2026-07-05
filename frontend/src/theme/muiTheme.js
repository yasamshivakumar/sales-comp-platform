import { createTheme, alpha } from "@mui/material/styles";

const enterprise = {
  navy: "#032d60",
  navyDark: "#001639",
  accent: "#0176d3",
  accentLight: "#1b96ff",
};

export function buildMuiTheme(mode = "light") {
  const isDark = mode === "dark";

  return createTheme({
    palette: {
      mode,
      primary: {
        main: enterprise.accent,
        light: enterprise.accentLight,
        dark: "#014486",
        contrastText: "#fff",
      },
      secondary: {
        main: enterprise.navy,
        light: "#1a4480",
        dark: enterprise.navyDark,
        contrastText: "#fff",
      },
      success: {
        main: isDark ? "#3ecf8e" : "#067647",
        light: isDark ? "#065f46" : "#ecfdf3",
        dark: "#047857",
      },
      warning: {
        main: isDark ? "#fbbf24" : "#b54708",
        light: isDark ? "#78350f" : "#fffaeb",
      },
      error: {
        main: isDark ? "#f87171" : "#b42318",
        light: isDark ? "#7f1d1d" : "#fef3f2",
      },
      info: {
        main: enterprise.accent,
        light: isDark ? "#0c4a6e" : "#eff6ff",
      },
      background: {
        default: isDark ? "#0b1220" : "#f4f6f9",
        paper: isDark ? "#111827" : "#ffffff",
      },
      text: {
        primary: isDark ? "#f3f4f6" : "#181818",
        secondary: isDark ? "#9ca3af" : "#444444",
      },
      divider: isDark ? "rgba(148, 163, 184, 0.14)" : "#dddbda",
    },
    typography: {
      fontFamily: '"Inter", "Segoe UI", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: { fontWeight: 700, fontSize: "1.625rem", letterSpacing: "-0.025em", lineHeight: 1.25 },
      h2: { fontWeight: 700, fontSize: "1.25rem", letterSpacing: "-0.02em" },
      h3: { fontWeight: 600, fontSize: "1.0625rem" },
      subtitle1: { fontWeight: 600, fontSize: "0.9375rem" },
      subtitle2: { fontWeight: 700, fontSize: "0.8125rem", letterSpacing: "0.02em" },
      body2: { fontSize: "0.875rem", lineHeight: 1.55 },
      caption: { fontSize: "0.75rem", letterSpacing: "0.02em" },
      button: { textTransform: "none", fontWeight: 600, letterSpacing: "0.01em" },
    },
    shape: { borderRadius: 8 },
    shadows: [
      "none",
      isDark ? "0 1px 2px rgba(0,0,0,0.4)" : "0 1px 2px rgba(3,45,96,0.06)",
      isDark ? "0 2px 8px rgba(0,0,0,0.35)" : "0 2px 8px rgba(3,45,96,0.08)",
      isDark ? "0 4px 16px rgba(0,0,0,0.4)" : "0 4px 16px rgba(3,45,96,0.1)",
      ...Array(21).fill(isDark ? "0 8px 24px rgba(0,0,0,0.45)" : "0 8px 24px rgba(3,45,96,0.12)"),
    ],
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarColor: isDark ? "#475569 transparent" : "#cbd5e1 transparent",
            color: isDark ? "#f3f4f6" : "#0f172a",
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 6, padding: "7px 16px", minHeight: 36 },
          containedPrimary: {
            background: `linear-gradient(180deg, ${enterprise.accentLight} 0%, ${enterprise.accent} 100%)`,
            "&:hover": {
              background: `linear-gradient(180deg, ${enterprise.accentLight} 0%, #0161b3 100%)`,
            },
          },
          outlined: {
            borderColor: isDark ? alpha("#fff", 0.2) : "#c9c7c5",
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            border: `1px solid ${isDark ? alpha("#fff", 0.08) : "#dddbda"}`,
            boxShadow: isDark
              ? "0 2px 12px rgba(0,0,0,0.35)"
              : "0 2px 8px rgba(3, 45, 96, 0.06)",
            borderRadius: 10,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          rounded: { borderRadius: 10 },
        },
      },
      MuiTableHead: {
        styleOverrides: {
          root: {
            bgcolor: isDark ? alpha("#fff", 0.04) : "#f3f4f6",
            "& .MuiTableCell-head": {
              fontWeight: 700,
              fontSize: "0.6875rem",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: isDark ? "#9ca3af" : "#444444",
              borderBottom: `1px solid ${isDark ? alpha("#fff", 0.08) : "#dddbda"}`,
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderColor: isDark ? alpha("#fff", 0.08) : "#ecebea",
            fontSize: "0.875rem",
          },
        },
      },
      MuiTextField: {
        defaultProps: { size: "small", fullWidth: true },
        styleOverrides: {
          root: {
            "& .MuiOutlinedInput-root": {
              borderRadius: 6,
              bgcolor: isDark ? alpha("#fff", 0.03) : "#fff",
            },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            "&.Mui-disabled": {
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: isDark ? alpha("#fff", 0.12) : undefined,
              },
            },
          },
          input: {
            color: isDark ? "#f3f4f6" : "#0f172a",
            WebkitTextFillColor: isDark ? "#f3f4f6" : undefined,
            "&.Mui-disabled": {
              color: isDark ? alpha("#f3f4f6", 0.55) : undefined,
              WebkitTextFillColor: isDark ? alpha("#f3f4f6", 0.55) : undefined,
            },
          },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: {
            color: isDark ? "#9ca3af" : "#475569",
            "&.Mui-focused": {
              color: isDark ? enterprise.accentLight : enterprise.accent,
            },
            "&.Mui-disabled": {
              color: isDark ? alpha("#9ca3af", 0.72) : undefined,
            },
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: {
            color: isDark ? "#f3f4f6" : "#0f172a",
          },
        },
      },
      MuiDialogContentText: {
        styleOverrides: {
          root: {
            color: isDark ? "#cbd5e1" : "#475569",
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 600 },
          sizeSmall: { fontSize: "0.6875rem", letterSpacing: "0.06em" },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            "&:hover": {
              backgroundColor: "transparent",
            },
          },
        },
      },
    },
  });
}

export { enterprise };
