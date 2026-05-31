import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "./api";
import { useToast } from "./Components/Toast";

const apiHost = process.env.REACT_APP_API_HOST || "http://localhost:8000";
const oidcEnabled = process.env.REACT_APP_OIDC_ENABLED === "true";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { success, error } = useToast();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      localStorage.setItem("token", token);
      success("SSO login successful! Redirecting...");
      window.history.replaceState({}, "", "/login");
      setTimeout(() => navigate("/"), 800);
    }
  }, [navigate, success]);

  const handleLogin = async () => {
    if (!email || !password) {
      error("Please enter email and password");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      error("Please enter a valid email address");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("email-login/", { email, password });
      localStorage.setItem("token", res.data.token);
      localStorage.setItem("email", res.data.email);
      localStorage.setItem("user_id", res.data.user_id);
      localStorage.setItem("role", res.data.role);
      localStorage.setItem("name", res.data.name);
      success("Login successful! Redirecting...");
      setTimeout(() => navigate("/"), 1000);
    } catch (err) {
      error(err.response?.data?.error || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && email && password) {
      handleLogin();
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-page__bg" aria-hidden="true" />

      <div className="auth-card">
        <div className="auth-card__brand">
          <div className="auth-card__logo">⚡</div>
          <h2 className="auth-card__title">Welcome back</h2>
          <p className="auth-card__subtitle">Sign in to IncentivePro</p>
        </div>

        <div className="auth-form">
          <div className="auth-form__group">
            <label className="auth-form__label" htmlFor="login-email">
              Email address
            </label>
            <input
              id="login-email"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>

          <div className="auth-form__group">
            <label className="auth-form__label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>

          <button
            type="button"
            className="btn-primary auth-form__submit"
            onClick={handleLogin}
            disabled={loading}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </div>

        {oidcEnabled && (
          <div className="auth-form" style={{ marginTop: "1rem" }}>
            <button
              type="button"
              className="btn-secondary"
              style={{ width: "100%" }}
              onClick={() => {
                window.location.href = `${apiHost}/oidc/authenticate/`;
              }}
            >
              Sign in with SSO
            </button>
          </div>
        )}

        <div className="auth-card__footer">
          Don&apos;t have an account?{" "}
          <Link to="/signup">Create one</Link>
        </div>
      </div>
    </div>
  );
}

export default Login;
