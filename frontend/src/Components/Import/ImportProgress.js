import { Box, CircularProgress, LinearProgress, Typography } from "@mui/material";

const LABELS = {
  uploading: "Uploading…",
  validating: "Validating…",
  importing: "Importing…",
};

/**
 * Progress panel shown while validate/import requests run.
 */
export default function ImportProgress({ phase = "validating", percent = null }) {
  const label = LABELS[phase] || "Working…";
  const determinate = typeof percent === "number";

  return (
    <Box className="imp-progress" role="status" aria-live="polite">
      <CircularProgress size={36} thickness={4} />
      <Typography variant="subtitle1" sx={{ mt: 1.5, fontWeight: 600 }}>
        {label}
      </Typography>
      <Box sx={{ width: "100%", mt: 2 }}>
        <LinearProgress
          variant={determinate ? "determinate" : "indeterminate"}
          value={determinate ? percent : undefined}
        />
        {determinate ? (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.75, display: "block" }}>
            {Math.round(percent)}%
          </Typography>
        ) : null}
      </Box>
    </Box>
  );
}
