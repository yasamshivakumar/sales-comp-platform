import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, InputAdornment } from "@mui/material";
import SecurityIcon from "@mui/icons-material/Security";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import api, {
  getApiErrorMessage,
  getAuthToken,
  getOrCreateDeviceId,
  isSessionExpired,
  saveAuthSession,
} from "./api";
import { useToast } from "./Components/Toast";
import AuthTextField, { forceReadableAutofill } from "./Components/AuthTextField";
import "./Login.css";

const apiHost = process.env.REACT_APP_API_HOST || "http://localhost:8000";
const oidcEnabled = process.env.REACT_APP_OIDC_ENABLED === "true";

const LOGIN_AUTOFILL_STYLE_ID = "incentra-login-autofill-fix";

const LOGIN_AUTOFILL_CSS = `
@keyframes incentra-autofill-start { from { opacity: 0.99; } to { opacity: 1; } }
@keyframes incentra-autofill-cancel { from { opacity: 0.99; } to { opacity: 1; } }
.login-glass input:-webkit-autofill,
.login-glass input:-webkit-autofill:hover,
.login-glass input:-webkit-autofill:focus,
.login-glass input:-webkit-autofill:active {
  -webkit-text-fill-color: #0f172a !important;
  color: #0f172a !important;
  caret-color: #0f172a !important;
  background-color: #ffffff !important;
  background-image: none !important;
  -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
  box-shadow: 0 0 0 1000px #ffffff inset !important;
  filter: none !important;
  opacity: 1 !important;
  transition: background-color 99999s ease-in-out 0s !important;
  animation-name: incentra-autofill-start !important;
  animation-duration: 0.001s !important;
}
.login-glass input:not(:-webkit-autofill) {
  animation-name: incentra-autofill-cancel !important;
  animation-duration: 0.001s !important;
}
.login-glass .MuiOutlinedInput-root,
.login-glass .MuiInputBase-root,
.login-glass .auth-text-field .MuiOutlinedInput-root,
.login-glass .auth-text-field .MuiInputBase-root {
  background-color: #ffffff !important;
  min-height: 48px !important;
  box-sizing: border-box !important;
  border-radius: 12px !important;
}
.login-glass .MuiOutlinedInput-input,
.login-glass .MuiInputBase-input,
.login-glass .auth-text-field .MuiOutlinedInput-input,
.login-glass .auth-text-field .MuiInputBase-input,
.login-glass .auth-text-field input {
  color: #0f172a !important;
  -webkit-text-fill-color: #0f172a !important;
  caret-color: #0f172a !important;
  background-color: #ffffff !important;
  opacity: 1 !important;
  padding: 12px 14px !important;
  font-size: 0.95rem !important;
  line-height: 1.35 !important;
  height: auto !important;
  box-sizing: border-box !important;
}
`;

/** Keep autofilled credentials readable + same size as Login.css on white fields */
const loginFieldSx = {
  "& .MuiOutlinedInput-root": {
    backgroundColor: "#ffffff !important",
    minHeight: "48px !important",
    borderRadius: "12px !important",
  },
  "& .MuiOutlinedInput-input": {
    color: "#0f172a !important",
    WebkitTextFillColor: "#0f172a !important",
    caretColor: "#0f172a !important",
    backgroundColor: "#ffffff !important",
    padding: "12px 14px !important",
    fontSize: "0.95rem !important",
    lineHeight: "1.35 !important",
    height: "auto !important",
    boxSizing: "border-box !important",
  },
  "& .MuiOutlinedInput-input:-webkit-autofill": {
    WebkitTextFillColor: "#0f172a !important",
    WebkitBoxShadow: "0 0 0 1000px #ffffff inset !important",
    boxShadow: "0 0 0 1000px #ffffff inset !important",
    caretColor: "#0f172a !important",
    transition: "background-color 99999s ease-out 0s",
    padding: "12px 14px !important",
    fontSize: "0.95rem !important",
  },
};

const readableHtmlInputProps = {
  style: {
    color: "#0f172a",
    WebkitTextFillColor: "#0f172a",
    caretColor: "#0f172a",
    backgroundColor: "#ffffff",
  },
  onAnimationStart: (e) => {
    if (
      e.animationName === "incentra-autofill-start" ||
      String(e.animationName || "").toLowerCase().includes("autofill")
    ) {
      forceReadableAutofill(e.target);
    }
  },
};

function hasValidSession() {
  return Boolean(getAuthToken()) && !isSessionExpired();
}

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [mfaToken, setMfaToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const navigate = useNavigate();
  const { success, error } = useToast();

  // Production (Vercel) CSS chunk order lets dark-theme autofill win; inject last.
  useEffect(() => {
    let style = document.getElementById(LOGIN_AUTOFILL_STYLE_ID);
    if (!style) {
      style = document.createElement("style");
      style.id = LOGIN_AUTOFILL_STYLE_ID;
      style.setAttribute("data-purpose", "login-autofill-contrast");
      style.textContent = LOGIN_AUTOFILL_CSS;
    }
    // Always move to end of <head> so it beats Emotion/MUI production chunks.
    document.head.appendChild(style);

    const fixAll = () => {
      document.querySelectorAll(".login-glass input").forEach(forceReadableAutofill);
    };
    fixAll();
    const t1 = window.setTimeout(fixAll, 50);
    const t2 = window.setTimeout(fixAll, 300);
    const t3 = window.setTimeout(fixAll, 1000);
    const onFocusIn = (e) => {
      if (e.target?.closest?.(".login-glass")) forceReadableAutofill(e.target);
    };
    document.addEventListener("focusin", onFocusIn);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      window.clearTimeout(t3);
      document.removeEventListener("focusin", onFocusIn);
      style?.remove();
    };
  }, []);

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

  const finishLogin = (data) => {
    saveAuthSession(data);
    if (data.device_id) {
      localStorage.setItem("incentra_device_id", data.device_id);
    }
    success({
      title: "Welcome back",
      message: data.must_change_password
        ? "Please update your password to continue."
        : `Signed in as ${data.name || data.email}.`,
    });
    navigate("/dashboard", { replace: true });
  };

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
        device_id: getOrCreateDeviceId(),
        remember_device: true,
      });
      if (res.data?.mfa_required) {
        setMfaToken(res.data.mfa_token || "");
        setMfaCode("");
        success({
          title: "Authenticator required",
          message: "Enter the 6-digit code from your authenticator app.",
        });
        return;
      }
      finishLogin(res.data);
    } catch (err) {
      error({
        title: "Sign in failed",
        message: getApiErrorMessage(err, "We couldn't verify your credentials. Try again."),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleMfaVerify = async () => {
    if (!mfaCode.trim()) {
      error({ title: "Code required", message: "Enter your authenticator code." });
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("auth/mfa/verify/", {
        mfa_token: mfaToken,
        code: mfaCode.trim(),
        remember_device: true,
        device_id: getOrCreateDeviceId(),
      });
      setMfaToken("");
      setMfaCode("");
      finishLogin(res.data);
    } catch (err) {
      const nextToken = err.response?.data?.mfa_token;
      if (nextToken) setMfaToken(nextToken);
      error({
        title: "Verification failed",
        message: getApiErrorMessage(err, "Invalid authenticator code."),
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
            <h1 className="login-glass__title">{mfaToken ? "Verify" : "Login"}</h1>
            <p className="login-glass__subtitle">
              {mfaToken
                ? "Enter the code from your authenticator app"
                : "Access your Incentra workspace"}
            </p>

            {!mfaToken ? (
              <>
                <AuthTextField
                  label="Email"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !loading && handleLogin()}
                  autoComplete="email"
                  disabled={loading}
                  inputProps={readableHtmlInputProps}
                  sx={{ mb: 2, ...loginFieldSx }}
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
                  inputProps={readableHtmlInputProps}
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
                          }}
                        >
                          {showPassword ? (
                            <VisibilityOffIcon fontSize="small" />
                          ) : (
                            <VisibilityIcon fontSize="small" />
                          )}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                  sx={{ mb: 1, ...loginFieldSx }}
                />
                <button
                  type="button"
                  className="login-glass__submit"
                  disabled={loading}
                  onClick={handleLogin}
                >
                  {loading ? "Signing in…" : "Sign in"}
                </button>
              </>
            ) : (
              <>
                <AuthTextField
                  label="Authenticator code"
                  type="text"
                  placeholder="123456"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !loading && handleMfaVerify()}
                  autoComplete="one-time-code"
                  disabled={loading}
                  inputProps={readableHtmlInputProps}
                  sx={{ mb: 1, ...loginFieldSx }}
                />
                <button
                  type="button"
                  className="login-glass__submit"
                  disabled={loading}
                  onClick={handleMfaVerify}
                >
                  {loading ? "Verifying…" : "Verify & continue"}
                </button>
                <button
                  type="button"
                  className="login-glass__submit"
                  style={{
                    marginTop: 8,
                    background: "transparent",
                    boxShadow: "none",
                    border: "1px solid rgba(255,255,255,0.35)",
                  }}
                  onClick={() => {
                    setMfaToken("");
                    setMfaCode("");
                  }}
                  disabled={loading}
                >
                  Back
                </button>
              </>
            )}

            {oidcEnabled && !mfaToken && (
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
              New here? <strong>Accept your email invite</strong> to set a password before signing
              in.
            </p>
          </Box>
        </div>
      </div>
    </div>
  );
}

export default Login;
