import { useState } from "react";
import { useNavigate, Link as RouterLink } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CircularProgress,
  IconButton,
  InputAdornment,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import api, { getApiErrorMessage } from "./api";
import { useToast } from "./Components/Toast";
import AuthTextField from "./Components/AuthTextField";
import AuthPageLayout, { authFormCardSx } from "./Components/AuthPageLayout";

function Signup() {
  const [companyName, setCompanyName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { success, error } = useToast();

  const validateForm = () => {
    if (!companyName || !username || !email || !password || !confirmPassword) {
      error({ title: "Required fields", message: "All fields must be completed." });
      return false;
    }
    if (password !== confirmPassword) {
      error({ title: "Password mismatch", message: "New password and confirmation do not match." });
      return false;
    }
    if (password.length < 6) {
      error({ title: "Weak password", message: "Password must be at least 6 characters." });
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      error({ title: "Invalid email", message: "Enter a valid email address." });
      return false;
    }
    return true;
  };

  const handleSignup = async () => {
    if (!validateForm()) return;
    setLoading(true);
    try {
      await api.post("auth/signup/", {
        organization_name: companyName.trim(),
        username,
        email: email.trim().toLowerCase(),
        password,
      });
      success({
        title: "Account created",
        message: "Redirecting to sign in…",
      });
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      error({
        title: "Signup failed",
        message: getApiErrorMessage(err, "Could not create your account. Try again."),
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
        Join Incentra
      </Typography>
      <Typography sx={{ color: "rgba(255,255,255,0.78)", lineHeight: 1.7 }}>
        Create your account to manage compensation plans, commissions, and payouts.
      </Typography>
    </>
  );

  return (
    <AuthPageLayout brand={brandPanel}>
      <Card elevation={0} sx={authFormCardSx}>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          Create account
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Set up your Incentra credentials
        </Typography>

        <Stack spacing={2}>
          <AuthTextField
            label="Company name"
            placeholder="Example: Acme Sales Pvt Ltd"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSignup()}
            disabled={loading}
            autoComplete="organization"
          />
          <AuthTextField
            label="Username"
            placeholder="Choose a username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSignup()}
            disabled={loading}
            autoComplete="username"
          />
          <AuthTextField
            label="Email"
            type="email"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSignup()}
            disabled={loading}
            autoComplete="email"
          />
          <AuthTextField
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="At least 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSignup()}
            disabled={loading}
            autoComplete="new-password"
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
          <AuthTextField
            label="Confirm password"
            type={showConfirmPassword ? "text" : "password"}
            placeholder="Re-enter password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSignup()}
            disabled={loading}
            autoComplete="new-password"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                    aria-pressed={showConfirmPassword}
                    edge="end"
                    size="small"
                    type="button"
                    onClick={() => setShowConfirmPassword((value) => !value)}
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
                    {showConfirmPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={handleSignup}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={18} color="inherit" /> : null}
            sx={{ mt: 0.5 }}
          >
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </Stack>

        <Typography align="center" sx={{ mt: 3 }} color="text.secondary" variant="body2">
          Already have an account?{" "}
          <Link component={RouterLink} to="/login" fontWeight={700}>
            Sign in
          </Link>
        </Typography>
      </Card>
    </AuthPageLayout>
  );
}

export default Signup;
