import { Box, TextField, Typography } from "@mui/material";

/**
 * Force readable autofill text on white login fields (Chrome/Edge production builds
 * often let dark-theme autofill win and paint light text on white).
 */
export function forceReadableAutofill(el) {
  if (!el || el.nodeType !== 1) return;
  el.style.setProperty("color", "#0f172a", "important");
  el.style.setProperty("-webkit-text-fill-color", "#0f172a", "important");
  el.style.setProperty("caret-color", "#0f172a", "important");
  el.style.setProperty("background-color", "#ffffff", "important");
  el.style.setProperty("-webkit-box-shadow", "0 0 0 1000px #ffffff inset", "important");
  el.style.setProperty("box-shadow", "0 0 0 1000px #ffffff inset", "important");
  el.style.setProperty("filter", "none", "important");
  el.style.setProperty("opacity", "1", "important");
}

/** Static label above field — avoids overlap with global input CSS */
function AuthTextField({ label, id, sx, InputProps, slotProps, className, inputProps, ...props }) {
  const fieldId = id || label?.toLowerCase().replace(/\s+/g, "-");
  const inputSlot = {
    ...(slotProps?.input || {}),
    ...(InputProps || {}),
  };
  const htmlInput = {
    ...(slotProps?.htmlInput || {}),
    ...(inputProps || {}),
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
          htmlInput,
        }}
        {...props}
      />
    </Box>
  );
}

export default AuthTextField;
