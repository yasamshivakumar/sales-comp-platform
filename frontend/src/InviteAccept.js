import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  IconButton,
  InputAdornment,
  Stack,
  Typography,
} from "@mui/material";
import BoltIcon from "@mui/icons-material/Bolt";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import api, { getApiErrorMessage } from "./api";
import AuthTextField from "./Components/AuthTextField";
import AuthPageLayout, { authFormCardSx } from "./Components/AuthPageLayout";
import LoadingCenter from "./Components/LoadingCenter";
import { useToast } from "./Components/Toast";
import { enterprise } from "./theme/muiTheme";

const visibilityButtonSx = {
  width: "32px !important",
  minWidth: "32px !important",
  height: "32px",
  p: "4px !important",
  bgcolor: "transparent !important",
  boxShadow: "none !important",
  color: "text.secondary",
  "&:hover": {
    bgcolor: "action.hover !important",
    transform: "none",
  },
};

function PasswordToggle({ visible, onToggle, label }) {
  return (
    <InputAdornment position="end">
      <IconButton
        aria-label={visible ? `Hide ${label}` : `Show ${label}`}
        aria-pressed={visible}
        edge="end"
        size="small"
        type="button"
        onClick={onToggle}
        onMouseDown={(e) => e.preventDefault()}
        sx={visibilityButtonSx}
      >
        {visible ? <VisibilityOffIcon /> : <VisibilityIcon />}
      </IconButton>
    </InputAdornment>
  );
}

function InviteAccept() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .get(`auth/invite/${token}/`)
      .then((res) => {
        if (active) setInvite(res.data);
      })
      .catch((err) => {
        if (active) {
          error({
            title: "Invite unavailable",
            message: getApiErrorMessage(err, "This invite is invalid or expired."),
          });
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, error]);

  const handleSubmit = async () => {
    if (password.length < 8) {
      error({ title: "Weak password", message: "Password must be at least 8 characters." });
      return;
    }
    if (password !== confirmPassword) {
      error({ title: "Password mismatch", message: "Password and confirmation do not match." });
      return;
    }

    setSubmitting(true);
    try {
      await api.post(`auth/invite/${token}/accept/`, {
        password,
        confirm_password: confirmPassword,
      });
      success({
        title: "Password set",
        message: "Your account is active. Sign in with your email and new password.",
      });
      setTimeout(() => navigate("/login"), 900);
    } catch (err) {
      error({
        title: "Could not accept invite",
        message: getApiErrorMessage(err, "Invite could not be accepted."),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const brandPanel = (
    <>
      <Box
        sx={{
          width: 52,
          height: 52,
          borderRadius: 2,
          bgcolor: enterprise.accent,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          mb: 3,
          boxShadow: "0 8px 24px rgba(1,118,211,0.35)",
        }}
      >
        <BoltIcon />
      </Box>
      <Typography
        variant="h3"
        fontWeight={800}
        sx={{ mb: 1.5, lineHeight: 1.2, color: "#fff" }}
      >
        Welcome to Incentra
      </Typography>
      <Typography sx={{ color: "rgba(255,255,255,0.78)", lineHeight: 1.7 }}>
        Set your password from the secure invite sent by your company admin.
      </Typography>
    </>
  );

  return (
    <AuthPageLayout brand={brandPanel}>
      <Card elevation={0} sx={authFormCardSx}>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          Accept invite
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          {invite
            ? `${invite.name} · ${invite.organization_name}`
            : "Validate your invite and set your password."}
        </Typography>

        {loading ? (
          <LoadingCenter label="Checking your invite…" minHeight={200} />
        ) : invite ? (
          <Stack spacing={2}>
            <AuthTextField label="Email" value={invite.email || ""} disabled />
            <AuthTextField
              label="Password"
              type={showPassword ? "text" : "password"}
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              autoComplete="new-password"
              InputProps={{
                endAdornment: (
                  <PasswordToggle
                    visible={showPassword}
                    onToggle={() => setShowPassword((value) => !value)}
                    label="password"
                  />
                ),
              }}
            />
            <AuthTextField
              label="Confirm password"
              type={showConfirmPassword ? "text" : "password"}
              placeholder="Re-enter password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              autoComplete="new-password"
              InputProps={{
                endAdornment: (
                  <PasswordToggle
                    visible={showConfirmPassword}
                    onToggle={() => setShowConfirmPassword((value) => !value)}
                    label="confirm password"
                  />
                ),
              }}
            />
            <Button
              variant="contained"
              size="large"
              fullWidth
              onClick={handleSubmit}
              disabled={submitting}
              startIcon={submitting ? <CircularProgress size={18} color="inherit" /> : null}
            >
              {submitting ? "Activating..." : "Set password"}
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Typography color="text.secondary">
              This invite is invalid, expired, or already used. Ask your admin to resend an invite.
            </Typography>
            <Button variant="outlined" onClick={() => navigate("/login")}>
              Back to sign in
            </Button>
          </Stack>
        )}
      </Card>
    </AuthPageLayout>
  );
}

export default InviteAccept;
