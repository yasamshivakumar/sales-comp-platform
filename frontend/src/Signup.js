import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import api from "./api";
import { useToast } from "./Components/Toast";

function Signup() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();
  const { success, error } = useToast();

  const validateForm = () => {
    if (!username || !email || !password || !confirmPassword) {
      error("All fields are required");
      return false;
    }
    if (password !== confirmPassword) {
      error("Passwords do not match");
      return false;
    }
    if (password.length < 6) {
      error("Password must be at least 6 characters");
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      error("Please enter a valid email");
      return false;
    }
    return true;
  };

  const handleSignup = async () => {
    if (!validateForm()) return;

    setLoading(true);
    try {
      await api.post("signup/", { username, email, password });
      success("Account created! Redirecting to login...");
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      error(err.response?.data?.error || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && username && email && password && confirmPassword) {
      handleSignup();
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-page__bg" aria-hidden="true" />

      <div className="auth-card">
        <div className="auth-card__brand">
          <div className="auth-card__logo">⚡</div>
          <h2 className="auth-card__title">Create account</h2>
          <p className="auth-card__subtitle">Join IncentivePro today</p>
        </div>

        <div className="auth-form">
          <div className="auth-form__group">
            <label className="auth-form__label" htmlFor="signup-username">
              Username
            </label>
            <input
              id="signup-username"
              type="text"
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>

          <div className="auth-form__group">
            <label className="auth-form__label" htmlFor="signup-email">
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>

          <div className="auth-form__group">
            <label className="auth-form__label" htmlFor="signup-password">
              Password
            </label>
            <input
              id="signup-password"
              type="password"
              placeholder="At least 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>

          <div className="auth-form__group">
            <label className="auth-form__label" htmlFor="signup-confirm">
              Confirm password
            </label>
            <input
              id="signup-confirm"
              type="password"
              placeholder="Re-enter password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
          </div>

          <button
            type="button"
            className="btn-primary auth-form__submit"
            onClick={handleSignup}
            disabled={loading}
          >
            {loading ? "Creating account…" : "Create account"}
          </button>
        </div>

        <div className="auth-card__footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

export default Signup;
