import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, InputAdornment } from "@mui/material";
import SecurityIcon from "@mui/icons-material/Security";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import api, { getApiErrorMessage, getAuthToken, isSessionExpired, saveAuthSession } from "./api";
import { useToast } from "./Components/Toast";
import AuthTextField from "./Components/AuthTextField";
import "./Login.css";

const apiHost = process.env.REACT_APP_API_HOST || "http://localhost:8000";
const oidcEnabled = process.env.REACT_APP_OIDC_ENABLED === "true";

function hasValidSession() {
  return Boolean(getAuthToken()) && !isSessionExpired();
}

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { success, error } = useToast();

  useEffect(() => {
    if (hasValidSession()) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate]);

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
        saveAuthSession(res.data);
        success({
          title: "SSO sign-in complete",
          message: "Redirecting to your workspace…",
        });
        window.history.replaceState({}, "", "/login");
        navigate("/dashboard", { replace: true });
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
        message: `Signed in as ${res.data.name || res.data.email}.`,
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      error({
        title: "Sign in failed",
        message: getApiErrorMessage(err, "We couldn't verify your credentials. Try again."),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-glass">
      <div className="login-glass__stage" aria-hidden={false}>
        <span className="login-glass__blob login-glass__blob--a" aria-hidden="true" />
        <span className="login-glass__blob login-glass__blob--b" aria-hidden="true" />
        <span className="login-glass__blob login-glass__blob--c" aria-hidden="true" />
        <span className="login-glass__ribbon login-glass__ribbon--1" aria-hidden="true" />
        <span className="login-glass__ribbon login-glass__ribbon--2" aria-hidden="true" />
        <span className="login-glass__zig login-glass__zig--1" aria-hidden="true" />
        <span className="login-glass__zig login-glass__zig--2" aria-hidden="true" />

        <div className="login-glass__content">
          <aside className="login-glass__intro">
            <div className="login-glass__brand login-glass__brand--intro">
              <img src="/incentra-icon.svg" alt="" />
              <span className="login-glass__brand-name">Incentra</span>
            </div>
            <h2 className="login-glass__headline">Enterprise sales compensation</h2>
            <p className="login-glass__lede">
              Plan incentives, calculate commissions, and pay reps with confidence — built for
              finance and sales ops teams.
            </p>
            <ul className="login-glass__features">
              <li>
                <TrendingUpIcon fontSize="small" aria-hidden="true" />
                <span>Real-time commission analytics</span>
              </li>
              <li>
                <SecurityIcon fontSize="small" aria-hidden="true" />
                <span>Role-based access &amp; audit trails</span>
              </li>
            </ul>
          </aside>

          <Box className="login-glass__card" sx={{ position: "relative", overflow: "hidden" }}>
            <h1 className="login-glass__title">Login</h1>
            <p className="login-glass__subtitle">Access your Incentra workspace</p>

            <AuthTextField
            label="Email"
            type="email"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleLogin()}
            autoComplete="email"
            disabled={loading}
            sx={{ mb: 2 }}
          />
          <AuthTextField
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleLogin()}
            autoComplete="current-password"
            disabled={loading}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    edge="end"
                    size="small"
                    type="button"
                    disabled={loading}
                    onClick={() => setShowPassword((value) => !value)}
                    onMouseDown={(e) => e.preventDefault()}
                    sx={{
                      width: "32px !important",
                      minWidth: "32px !important",
                      height: "32px",
                      p: "4px !important",
                      bgcolor: "transparent !important",
                      boxShadow: "none !important",
                      color: "#64748b",
                      "&:hover": {
                        bgcolor: "rgba(15, 23, 42, 0.06) !important",
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

          <button
            type="button"
            className="login-glass__submit"
            disabled={loading}
            onClick={handleLogin}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>

          {oidcEnabled && (
            <>
              <div className="login-glass__divider">or continue with</div>
              <button
                type="button"
                className="login-glass__sso"
                disabled={loading}
                onClick={() => {
                  window.location.href = `${apiHost}/oidc/authenticate/`;
                }}
              >
                Continue with SSO
              </button>
            </>
          )}

          <p className="login-glass__footer">
            New here? <strong>Accept your email invite</strong> to set a password before signing in.
          </p>
          </Box>
        </div>
      </div>
    </div>
  );
}

export default Login;
