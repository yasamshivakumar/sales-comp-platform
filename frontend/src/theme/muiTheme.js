import { createTheme, alpha } from "@mui/material/styles";
import { pickerSurfaceTokens } from "./datePickerTokens";

const enterprise = {
  navy: "#032d60",
  navyDark: "#001639",
  accent: "#0176d3",
  accentLight: "#1b96ff",
};

export { pickerSurfaceTokens } from "./datePickerTokens";

export function buildMuiTheme(mode = "light") {
  const isDark = mode === "dark";
  const pickerSurface = pickerSurfaceTokens(isDark);

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
        default: isDark ? "#0a1b33" : "#c5daf0",
        paper: isDark ? "rgba(17, 28, 48, 0.72)" : "rgba(255, 255, 255, 0.72)",
      },
      text: {
        primary: isDark ? "#f3f4f6" : "#181818",
        secondary: isDark ? "#9ca3af" : "#444444",
      },
      divider: isDark ? "rgba(148, 163, 184, 0.14)" : "#dddbda",
    },
    // Date pickers use theme.zIndex.modal on their Popper. Keep them above
    // every custom overlay in the app (drawers ~1300, integration modal ~1500).
    zIndex: {
      mobileStepper: 1000,
      fab: 1050,
      speedDial: 1050,
      appBar: 1100,
      drawer: 1200,
      modal: 2200,
      snackbar: 2300,
      tooltip: 2400,
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
            border: `1px solid ${isDark ? alpha("#fff", 0.14) : "rgba(255,255,255,0.55)"}`,
            boxShadow: isDark
              ? "0 16px 48px rgba(0,0,0,0.45)"
              : "0 12px 40px rgba(3, 45, 96, 0.12)",
            borderRadius: 16,
            backgroundImage: "none",
            backgroundColor: isDark
              ? "rgba(17, 28, 48, 0.55)"
              : "rgba(255, 255, 255, 0.55)",
            backdropFilter: "blur(18px) saturate(1.25)",
            WebkitBackdropFilter: "blur(18px) saturate(1.25)",
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          rounded: { borderRadius: 16 },
          root: {
            backgroundImage: "none",
          },
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

      // ---- Date pickers (glass) — visual details live in date-picker.css
      MuiPickersLayout: {
        styleOverrides: {
          root: {
            backgroundColor: "transparent",
            color: pickerSurface.text,
          },
          actionBar: {
            backgroundColor: pickerSurface.actionBar,
            borderTop: `1px solid ${pickerSurface.border}`,
            "& .MuiButton-root": {
              color: pickerSurface.accent,
              fontWeight: 700,
              textTransform: "none",
            },
          },
        },
      },
      MuiPickersPopper: {
        styleOverrides: {
          paper: {
            backgroundColor: pickerSurface.bg,
            backgroundImage: "none",
            color: pickerSurface.text,
            border: `1px solid ${pickerSurface.border}`,
            borderRadius: 16,
            backdropFilter: `blur(${pickerSurface.blur}) saturate(1.25)`,
            WebkitBackdropFilter: `blur(${pickerSurface.blur}) saturate(1.25)`,
            boxShadow: pickerSurface.shadow,
          },
        },
      },
      MuiDateCalendar: {
        styleOverrides: {
          root: {
            backgroundColor: "transparent",
            color: pickerSurface.text,
          },
        },
      },
      MuiDayCalendar: {
        styleOverrides: {
          weekDayLabel: {
            color: pickerSurface.muted,
            fontWeight: 700,
          },
        },
      },
      MuiPickersCalendarHeader: {
        styleOverrides: {
          root: { color: pickerSurface.text },
          label: { color: pickerSurface.text, fontWeight: 700 },
          switchViewButton: { color: pickerSurface.text },
        },
      },
      MuiPickersArrowSwitcher: {
        styleOverrides: {
          button: { color: pickerSurface.text },
        },
      },
      MuiPickersDay: {
        styleOverrides: {
          root: {
            color: pickerSurface.text,
            fontWeight: 600,
            "&:hover": { backgroundColor: pickerSurface.hover },
            "&.Mui-selected": {
              backgroundColor: pickerSurface.accent,
              color: pickerSurface.accentText,
              fontWeight: 700,
              "&:hover": { backgroundColor: pickerSurface.accentHover },
            },
            "&.Mui-disabled": { color: pickerSurface.disabled },
          },
          today: {
            borderColor: pickerSurface.accent,
            backgroundColor: pickerSurface.todayBg,
            color: pickerSurface.text,
          },
          dayOutsideMonth: { color: pickerSurface.outside },
        },
      },
      MuiPickersYear: {
        styleOverrides: {
          yearButton: {
            color: pickerSurface.text,
            "&.Mui-selected": {
              backgroundColor: pickerSurface.accent,
              color: pickerSurface.accentText,
            },
          },
        },
      },
      MuiPickersMonth: {
        styleOverrides: {
          monthButton: {
            color: pickerSurface.text,
            "&.Mui-selected": {
              backgroundColor: pickerSurface.accent,
              color: pickerSurface.accentText,
            },
          },
        },
      },
    },
  });
}

export { enterprise };
