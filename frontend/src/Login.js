import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CircularProgress,
  IconButton,
  InputAdornment,
  Stack,
  Typography,
} from "@mui/material";
import SecurityIcon from "@mui/icons-material/Security";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import api, { getApiErrorMessage, saveAuthSession } from "./api";
import { useToast } from "./Components/Toast";
import AuthTextField from "./Components/AuthTextField";
import AuthPageLayout, { authFormCardSx } from "./Components/AuthPageLayout";

const apiHost = process.env.REACT_APP_API_HOST || "http://localhost:8000";
const oidcEnabled = process.env.REACT_APP_OIDC_ENABLED === "true";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { success, error } = useToast();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ssoCode = params.get("sso_code");
    const ssoError = params.get("sso_error");

    if (ssoError) {
      error({
        title: "SSO sign-in failed",
        message: "Could not complete single sign-on. Please try again.",
      });
      window.history.replaceState({}, "", "/login");
      return;
    }

    if (!ssoCode) return undefined;

    let cancelled = false;
    (async () => {
      try {
        const res = await api.post("auth/oidc-exchange/", { code: ssoCode });
        if (cancelled) return;
        saveAuthSession({ token: res.data.token });
        success({
          title: "SSO sign-in complete",
          message: "Redirecting to your workspace…",
        });
        window.history.replaceState({}, "", "/login");
        setTimeout(() => navigate("/dashboard"), 800);
      } catch (err) {
        if (cancelled) return;
        error({
          title: "SSO sign-in failed",
          message: getApiErrorMessage(err, "Invalid or expired sign-in code."),
        });
        window.history.replaceState({}, "", "/login");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [navigate, success, error]);

  const handleLogin = async () => {
    if (!email || !password) {
      error({
        title: "Missing credentials",
        message: "Enter both your email address and password to continue.",
      });
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      error({
        title: "Invalid email",
        message: "Use a valid company email address (example: you@company.com).",
      });
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("auth/email-login/", {
        email: email.trim().toLowerCase(),
        password,
      });
      saveAuthSession(res.data);
      success({
        title: "Welcome back",
        message: `Signed in as ${res.data.name || res.data.email}. Opening dashboard…`,
      });
      setTimeout(() => navigate("/dashboard"), 1000);
    } catch (err) {
      error({
        title: "Sign in failed",
        message: getApiErrorMessage(err, "We couldn't verify your credentials. Try again."),
      });
    } finally {
      setLoading(false);
    }
  };

  const brandPanel = (
    <>
      <Box
        component="img"
        src="/incentra-icon.svg"
        alt="Incentra"
        sx={{
          width: 52,
          height: 52,
          borderRadius: 2,
          mb: 3,
          boxShadow: "0 8px 24px rgba(1,118,211,0.35)",
        }}
      />
      <Typography
        variant="h3"
        fontWeight={800}
        sx={{ mb: 1.5, lineHeight: 1.2, color: "#fff" }}
      >
        Enterprise sales compensation
      </Typography>
      <Typography sx={{ color: "rgba(255,255,255,0.78)", lineHeight: 1.7, mb: 4 }}>
        Plan incentives, calculate commissions, and pay reps with confidence — built for
        finance and sales ops teams.
      </Typography>
      <Stack spacing={2}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <TrendingUpIcon sx={{ color: "rgba(255,255,255,0.85)" }} />
          <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.86)" }}>
            Real-time commission analytics
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <SecurityIcon sx={{ color: "rgba(255,255,255,0.85)" }} />
          <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.86)" }}>
            Role-based access & audit trails
          </Typography>
        </Stack>
      </Stack>
    </>
  );

  return (
    <AuthPageLayout brand={brandPanel}>
      <Card elevation={0} sx={authFormCardSx}>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          Sign in
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Access your Incentra workspace
        </Typography>

        <Stack spacing={2}>
          <AuthTextField
            label="Work email"
            type="email"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            disabled={loading}
            autoComplete="email"
          />
          <AuthTextField
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="Enter your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            disabled={loading}
            autoComplete="current-password"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    edge="end"
                    size="small"
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    onMouseDown={(e) => e.preventDefault()}
                    sx={{
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
                    }}
                  >
                    {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={handleLogin}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={18} color="inherit" /> : null}
          >
            {loading ? "Signing in…" : "Sign in securely"}
          </Button>
        </Stack>

        {oidcEnabled && (
          <Button
            variant="outlined"
            fullWidth
            sx={{ mt: 2 }}
            onClick={() => {
              window.location.href = `${apiHost}/oidc/authenticate/`;
            }}
          >
            Continue with SSO
          </Button>
        )}

        <Typography align="center" sx={{ mt: 3 }} color="text.secondary" variant="body2">
          New employees must accept their email invite and set a password before signing in.
        </Typography>
      </Card>
    </AuthPageLayout>
  );
}

export default Login;
