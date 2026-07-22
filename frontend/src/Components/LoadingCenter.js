import { Box, CircularProgress } from "@mui/material";
import { enterprise } from "../theme/muiTheme";

/**
 * Centered loading spinner for cards / panels.
 * Use `overlay` to float over existing content without collapsing layout.
 */
function LoadingCenter({
  label = "",
  overlay = false,
  overlayTone = "light",
  minHeight = 160,
  size = 24,
}) {
  const content = (
    <Box
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={label || "Loading"}
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        minHeight: overlay ? "100%" : minHeight,
      }}
    >
      <CircularProgress
        size={size}
        thickness={4}
        sx={{ color: overlayTone === "dark" ? "#fff" : enterprise.accent }}
      />
    </Box>
  );

  if (!overlay) return content;

  return (
    <Box
      sx={{
        position: "absolute",
        inset: 0,
        zIndex: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "inherit",
        bgcolor:
          overlayTone === "dark"
            ? "rgba(3, 45, 96, 0.4)"
            : "rgba(255, 255, 255, 0.72)",
        backdropFilter: "blur(3px)",
        WebkitBackdropFilter: "blur(3px)",
      }}
    >
      {content}
    </Box>
  );
}

export default LoadingCenter;
