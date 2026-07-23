import { Box, TextField, Typography } from "@mui/material";

/** Static label above field — avoids overlap with global input CSS */
function AuthTextField({ label, id, sx, InputProps, slotProps, className, ...props }) {
  const fieldId = id || label?.toLowerCase().replace(/\s+/g, "-");
  // Prefer MUI slotProps.input for OutlinedInput props (endAdornment, etc.)
  const inputSlot = {
    ...(slotProps?.input || {}),
    ...(InputProps || {}),
  };

  return (
    <Box className="auth-text-field-wrap" sx={{ width: "100%", ...sx }}>
      <Typography
        component="label"
        htmlFor={fieldId}
        variant="body2"
        fontWeight={600}
        className="auth-text-field-label"
        sx={{ display: "block", mb: 0.75, color: "text.secondary" }}
      >
        {label}
      </Typography>
      <TextField
        id={fieldId}
        hiddenLabel
        fullWidth
        variant="outlined"
        size="small"
        className={`auth-text-field${className ? ` ${className}` : ""}`}
        slotProps={{
          ...slotProps,
          input: inputSlot,
        }}
        {...props}
      />
    </Box>
  );
}

export default AuthTextField;
