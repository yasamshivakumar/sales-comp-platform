/**
 * Single source of truth for date-picker glass surfaces.
 * Values must stay aligned with --dp-* in styles/date-picker.css
 * and the app glass tokens in styles/glass.css.
 */
export function pickerSurfaceTokens(isDark) {
  return isDark
    ? {
        bg: "rgba(10, 27, 51, 0.92)",
        text: "#f1f5f9",
        muted: "#94a3b8",
        border: "rgba(148, 163, 184, 0.28)",
        accent: "#1b96ff",
        accentHover: "#5bb8ff",
        accentText: "#ffffff",
        todayBg: "rgba(27, 150, 255, 0.2)",
        hover: "rgba(27, 150, 255, 0.16)",
        focusRing: "rgba(27, 150, 255, 0.45)",
        disabled: "#64748b",
        outside: "#475569",
        actionBar: "rgba(6, 20, 39, 0.94)",
        shadow:
          "0 24px 64px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(148, 163, 184, 0.2)",
        scrim: "rgba(2, 8, 20, 0.72)",
        blur: "22px",
      }
    : {
        bg: "rgba(232, 242, 252, 0.9)",
        text: "#0f172a",
        muted: "#475569",
        border: "rgba(3, 45, 96, 0.18)",
        accent: "#0176d3",
        accentHover: "#014486",
        accentText: "#ffffff",
        todayBg: "rgba(1, 118, 211, 0.14)",
        hover: "rgba(1, 118, 211, 0.12)",
        focusRing: "rgba(1, 118, 211, 0.35)",
        disabled: "#94a3b8",
        outside: "#94a3b8",
        actionBar: "rgba(214, 232, 248, 0.92)",
        shadow:
          "0 24px 56px rgba(3, 45, 96, 0.22), 0 2px 10px rgba(3, 45, 96, 0.1)",
        scrim: "rgba(3, 45, 96, 0.4)",
        blur: "20px",
      };
}
