import { Box, CircularProgress, Typography } from "@mui/material";
import { enterprise } from "../theme/muiTheme";

/**
 * Centered loading state for cards / panels.
 * Use `overlay` to float over existing content without collapsing layout.
 */
function LoadingCenter({
  label = "Loading…",
  overlay = false,
  minHeight = 220,
  size = 40,
}) {
  const content = (
    <Box
      role="status"
      aria-live="polite"
      aria-busy="true"
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 1.75,
        textAlign: "center",
        width: "100%",
        minHeight: overlay ? "100%" : minHeight,
        px: 2,
      }}
    >
      <Box
        sx={{
          position: "relative",
          width: size + 16,
          height: size + 16,
          display: "grid",
          placeItems: "center",
        }}
      >
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            background: `radial-gradient(circle, ${enterprise.accent}22 0%, transparent 70%)`,
          }}
        />
        <CircularProgress
          size={size}
          thickness={3.6}
          sx={{ color: enterprise.accent }}
        />
      </Box>
      {label ? (
        <Typography
          variant="body2"
          sx={{
            fontWeight: 600,
            letterSpacing: "0.02em",
            color: "text.secondary",
          }}
        >
          {label}
        </Typography>
      ) : null}
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
        bgcolor: "rgba(255, 255, 255, 0.78)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
      }}
    >
      {content}
    </Box>
  );
}

export default LoadingCenter;
