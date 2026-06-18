import React, { useState, useCallback, useRef } from "react";
import {
  Alert,
  AlertTitle,
  Box,
  IconButton,
  Paper,
  Slide,
  Stack,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import WarningIcon from "@mui/icons-material/Warning";
import InfoIcon from "@mui/icons-material/Info";

const TOAST_META = {
  success: {
    title: "Success",
    icon: CheckCircleIcon,
    accent: "#067647",
    bg: "#ecfdf3",
    border: "#abefc6",
    iconColor: "#067647",
  },
  error: {
    title: "Error",
    icon: ErrorIcon,
    accent: "#b42318",
    bg: "#fef3f2",
    border: "#fecdca",
    iconColor: "#b42318",
  },
  warning: {
    title: "Warning",
    icon: WarningIcon,
    accent: "#b54708",
    bg: "#fffaeb",
    border: "#fedf89",
    iconColor: "#b54708",
  },
  info: {
    title: "Information",
    icon: InfoIcon,
    accent: "#0176d3",
    bg: "#eff6ff",
    border: "#b9d9f7",
    iconColor: "#0176d3",
  },
};

function normalizeToast(input, type) {
  if (input && typeof input === "object" && !React.isValidElement(input)) {
    return {
      title: input.title || TOAST_META[type]?.title || "Notice",
      message: input.message || input.description || "",
      type: input.type || type,
      duration: input.duration,
    };
  }
  return {
    title: TOAST_META[type]?.title || "Notice",
    message: String(input ?? ""),
    type,
  };
}

function EnterpriseToast({ toast, onClose }) {
  const meta = TOAST_META[toast.type] || TOAST_META.info;
  const Icon = meta.icon;

  return (
    <Slide direction="left" in mountOnEnter unmountOnExit>
      <Paper
        elevation={8}
        role="alert"
        aria-live="polite"
        sx={{
          width: "100%",
          maxWidth: 400,
          minWidth: { xs: 280, sm: 360 },
          overflow: "hidden",
          borderRadius: 2,
          border: "1px solid",
          borderColor: meta.border,
          borderLeft: "4px solid",
          borderLeftColor: meta.accent,
          bgcolor: (theme) =>
          theme.palette.mode === "dark" ? "#1f2937" : meta.bg,
          boxShadow: "0 12px 40px rgba(3, 45, 96, 0.14)",
        }}
      >
        <Stack direction="row" spacing={1.5} sx={{ p: 1.75, pr: 1 }}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              bgcolor: (theme) =>
                theme.palette.mode === "dark"
                  ? `${meta.accent}22`
                  : `${meta.accent}14`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Icon sx={{ fontSize: 20, color: meta.iconColor }} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0, pt: 0.25 }}>
            <Typography variant="subtitle2" sx={{ color: meta.accent, mb: 0.25 }}>
              {toast.title}
            </Typography>
            <Typography variant="body2" color="text.primary" sx={{ lineHeight: 1.5 }}>
              {toast.message}
            </Typography>
          </Box>
          <IconButton
            size="small"
            aria-label="Dismiss notification"
            onClick={onClose}
            sx={{ alignSelf: "flex-start", color: "text.secondary" }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Paper>
    </Slide>
  );
}

export const ToastContainer = ({ toasts, removeToast }) => (
  <Stack
    spacing={1.5}
    sx={{
      position: "fixed",
      top: { xs: 16, md: 20 },
      right: { xs: 16, md: 24 },
      zIndex: 9999,
      pointerEvents: "none",
      "& > *": { pointerEvents: "auto" },
    }}
  >
    {toasts.map((toast) => (
      <EnterpriseToast
        key={toast.id}
        toast={toast}
        onClose={() => removeToast(toast.id)}
      />
    ))}
  </Stack>
);

export const ToastContext = React.createContext();

export const useToast = () => {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
};

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);
  const toastSeq = useRef(0);
  const timers = useRef({});

  const removeToast = useCallback((id) => {
    if (timers.current[id]) {
      clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback(
    (input, type = "info", duration = 5000) => {
      const normalized = normalizeToast(input, type);
      toastSeq.current += 1;
      const id = `${Date.now()}-${toastSeq.current}`;
      const toastDuration = normalized.duration ?? duration;

      setToasts((prev) => [...prev.slice(-4), { id, ...normalized }]);

      if (toastDuration > 0) {
        timers.current[id] = setTimeout(() => removeToast(id), toastDuration);
      }
      return id;
    },
    [removeToast]
  );

  const value = {
    addToast,
    removeToast,
    success: (input, duration = 5000) => addToast(input, "success", duration),
    error: (input, duration = 8000) => addToast(input, "error", duration),
    warning: (input, duration = 7000) => addToast(input, "warning", duration),
    info: (input, duration = 5000) => addToast(input, "info", duration),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
};

/** Inline enterprise alert for forms / panels */
export function EnterpriseAlert({ severity = "info", title, children, onClose, sx }) {
  return (
    <Alert
      severity={severity}
      variant="outlined"
      onClose={onClose}
      sx={{
        borderRadius: 2,
        borderLeftWidth: 4,
        borderLeftStyle: "solid",
        alignItems: "flex-start",
        ...sx,
      }}
    >
      {title && <AlertTitle sx={{ fontWeight: 700, mb: 0.5 }}>{title}</AlertTitle>}
      {children}
    </Alert>
  );
}

export default EnterpriseToast;
