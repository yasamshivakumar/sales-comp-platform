import { Box, TextField, Typography } from "@mui/material";

/** Static label above field — avoids overlap with global input CSS */
function AuthTextField({ label, id, sx, ...props }) {
  const fieldId = id || label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <Box sx={{ width: "100%", ...sx }}>
      <Typography
        component="label"
        htmlFor={fieldId}
        variant="body2"
        fontWeight={600}
        color="text.secondary"
        sx={{ display: "block", mb: 0.75 }}
      >
        {label}
      </Typography>
      <TextField
        id={fieldId}
        hiddenLabel
        fullWidth
        variant="outlined"
        size="small"
        {...props}
      />
    </Box>
  );
}

export default AuthTextField;
