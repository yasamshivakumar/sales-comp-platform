import axios from "axios";

function normalizeBaseUrl(url) {
  if (!url) return "";
  return String(url).trim().replace(/\/+$/, "");
}

const isDevelopment = process.env.NODE_ENV !== "production";

// Local dev: use "/api" + package.json proxy → avoids CORS issues
const envBase = normalizeBaseUrl(process.env.REACT_APP_API_BASE_URL);
const apiHost = normalizeBaseUrl(
  process.env.REACT_APP_API_HOST || "http://localhost:8000"
);
const apiBaseURL =
  envBase ||
  (isDevelopment ? "/api" : `${apiHost}/api`);

const isDebugEnabled = process.env.REACT_APP_DEBUG === "true";
const SESSION_EXPIRES_AT_KEY = "token_expires_at";
const SESSION_IDLE_MS_KEY = "session_idle_ms";
const DEFAULT_IDLE_MS = 60 * 60 * 1000; // 1 hour
const AUTH_STORAGE_KEYS = [
  "token",
  SESSION_EXPIRES_AT_KEY,
  SESSION_IDLE_MS_KEY,
  "username",
  "email",
  "role",
  "user_id",
  "name",
];
const PUBLIC_PATH_PREFIXES = ["/login", "/invite"];
const SESSION_EXPIRES_HEADER = "x-session-expires-at";
const ACTIVITY_HEARTBEAT_MS = 5 * 60 * 1000; // sync backend at most every 5 min
const ACTIVITY_THROTTLE_MS = 15 * 1000; // reset idle clock at most every 15s

let logoutTimer = null;
let logoutInProgress = false;
let lastActivityHandledAt = 0;
let lastHeartbeatAt = 0;
let heartbeatInFlight = false;

if (isDevelopment && isDebugEnabled) {
  console.log("[API] Host:", apiHost);
  console.log("[API] Base URL:", apiBaseURL);
}

const api = axios.create({
  baseURL: apiBaseURL,
  timeout: parseInt(process.env.REACT_APP_REQUEST_TIMEOUT_MS || "30000", 10),
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

function isPublicPath(pathname = window.location.pathname) {
  return PUBLIC_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

export function clearAuthStorage() {
  AUTH_STORAGE_KEYS.forEach((key) => {
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
  });
  window.dispatchEvent(new CustomEvent("auth-changed"));
}

function clearLegacyLocalAuthStorage() {
  AUTH_STORAGE_KEYS.forEach((key) => localStorage.removeItem(key));
}

function sessionExpiresAtMs() {
  const value = sessionStorage.getItem(SESSION_EXPIRES_AT_KEY);
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function sessionIdleMs() {
  const raw = Number(sessionStorage.getItem(SESSION_IDLE_MS_KEY));
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_IDLE_MS;
}

export function isSessionExpired() {
  const token = sessionStorage.getItem("token");
  if (!token) return false;
  const expiresAt = sessionExpiresAtMs();
  // Legacy sessions without expiry metadata must re-authenticate
  if (!expiresAt) return true;
  return Date.now() >= expiresAt;
}

export function logoutDueToSessionExpiry(reason = "session-expired") {
  if (logoutInProgress) return true;
  if (!sessionStorage.getItem("token")) return false;

  logoutInProgress = true;
  if (logoutTimer) {
    clearTimeout(logoutTimer);
    logoutTimer = null;
  }
  clearAuthStorage();
  window.dispatchEvent(new CustomEvent(reason));
  if (!isPublicPath()) {
    window.location.href = "/login";
  } else {
    logoutInProgress = false;
  }
  return true;
}

export function enforceValidSession() {
  if (!sessionStorage.getItem("token")) return false;
  if (isSessionExpired()) {
    logoutDueToSessionExpiry("session-expired");
    return false;
  }
  return true;
}

export function scheduleAutoLogout() {
  if (logoutTimer) {
    clearTimeout(logoutTimer);
    logoutTimer = null;
  }
  const expiresAt = sessionExpiresAtMs();
  if (!expiresAt) return;
  const delay = Math.max(expiresAt - Date.now(), 0);
  logoutTimer = setTimeout(() => {
    logoutDueToSessionExpiry("session-expired");
  }, delay);
}

function extendSessionExpiry(expiresAtIso) {
  if (!expiresAtIso || !sessionStorage.getItem("token")) return;
  const timestamp = Date.parse(expiresAtIso);
  if (Number.isNaN(timestamp)) return;
  sessionStorage.setItem(SESSION_EXPIRES_AT_KEY, expiresAtIso);
  scheduleAutoLogout();
}

function resetIdleExpiryFromActivity() {
  if (!sessionStorage.getItem("token")) return false;
  if (isSessionExpired()) {
    logoutDueToSessionExpiry("session-expired");
    return false;
  }
  const nextExpiry = new Date(Date.now() + sessionIdleMs()).toISOString();
  sessionStorage.setItem(SESSION_EXPIRES_AT_KEY, nextExpiry);
  scheduleAutoLogout();
  return true;
}

function sendSessionHeartbeat() {
  if (heartbeatInFlight || !sessionStorage.getItem("token") || isPublicPath()) {
    return;
  }
  heartbeatInFlight = true;
  lastHeartbeatAt = Date.now();
  api
    .get("auth/session/")
    .then((res) => {
      if (res.data?.token_expires_at) {
        extendSessionExpiry(res.data.token_expires_at);
      }
    })
    .catch(() => {
      // 401 interceptor handles forced logout
    })
    .finally(() => {
      heartbeatInFlight = false;
    });
}

/**
 * User is active: reset the 1-hour idle clock and occasionally sync the backend.
 */
export function noteUserActivity() {
  if (!sessionStorage.getItem("token") || isPublicPath()) return;

  const now = Date.now();
  if (now - lastActivityHandledAt < ACTIVITY_THROTTLE_MS) {
    return;
  }
  lastActivityHandledAt = now;

  if (!resetIdleExpiryFromActivity()) return;

  if (now - lastHeartbeatAt >= ACTIVITY_HEARTBEAT_MS) {
    sendSessionHeartbeat();
  }
}

export function saveAuthSession(data) {
  clearLegacyLocalAuthStorage();
  logoutInProgress = false;
  lastActivityHandledAt = 0;
  lastHeartbeatAt = 0;
  sessionStorage.setItem("token", data.token);
  sessionStorage.setItem("email", data.email || "");
  sessionStorage.setItem("user_id", data.user_id || "");
  sessionStorage.setItem("role", data.role || "");
  sessionStorage.setItem("name", data.name || "");
  if (data.token_expires_at) {
    const expiresMs = Date.parse(data.token_expires_at);
    const idleMs =
      Number.isFinite(expiresMs) && expiresMs > Date.now()
        ? expiresMs - Date.now()
        : DEFAULT_IDLE_MS;
    sessionStorage.setItem(SESSION_EXPIRES_AT_KEY, data.token_expires_at);
    sessionStorage.setItem(SESSION_IDLE_MS_KEY, String(idleMs));
  } else {
    sessionStorage.removeItem(SESSION_EXPIRES_AT_KEY);
    sessionStorage.removeItem(SESSION_IDLE_MS_KEY);
  }
  scheduleAutoLogout();
  window.dispatchEvent(new CustomEvent("auth-changed"));
}

export function getAuthToken() {
  if (isSessionExpired()) {
    logoutDueToSessionExpiry("session-expired");
    return null;
  }
  return sessionStorage.getItem("token");
}

export function getAuthSessionValue(key) {
  return sessionStorage.getItem(key);
}

api.interceptors.request.use((config) => {
  if (isSessionExpired()) {
    logoutDueToSessionExpiry("session-expired");
    return Promise.reject(new Error("Session expired. Please sign in again."));
  }
  const token = sessionStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    const expiresHeader = response.headers?.[SESSION_EXPIRES_HEADER];
    if (expiresHeader) {
      extendSessionExpiry(expiresHeader);
    } else if (response.data?.token_expires_at && sessionStorage.getItem("token")) {
      extendSessionExpiry(response.data.token_expires_at);
    }
    if (isDevelopment && isDebugEnabled) {
      console.log("[API] Response:", response.status, response.config.url);
    }
    return response;
  },
  (error) => {
    const requestUrl = error.config?.url || "";
    const isAuthRequest = /auth\/(email-login|oidc-exchange)\/?$/.test(requestUrl);

    if (error.response?.status === 401 && !isAuthRequest) {
      logoutDueToSessionExpiry("unauthorized");
    }

    if (isDevelopment && isDebugEnabled) {
      console.error("[API] Error:", error.response?.status, error.message);
    }

    return Promise.reject(error);
  }
);

clearLegacyLocalAuthStorage();
scheduleAutoLogout();

if (typeof window !== "undefined") {
  const onActivity = () => noteUserActivity();
  const onVisibility = () => {
    if (document.visibilityState === "visible") {
      if (!enforceValidSession()) return;
      noteUserActivity();
    }
  };

  window.addEventListener("focus", onVisibility);
  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("click", onActivity, true);
  window.addEventListener("keydown", onActivity, true);
  window.addEventListener("mousemove", onActivity, true);
  window.addEventListener("scroll", onActivity, true);
  window.addEventListener("touchstart", onActivity, true);
}

export function getApiErrorMessage(err, fallback = "Request failed") {
  if (!err.response) {
    return `Cannot reach API (${apiBaseURL}). Start the backend: cd backend → python manage.py runserver`;
  }
  const data = err.response.data;
  if (typeof data === "string") {
    if (data.trim().startsWith("<!DOCTYPE") || data.trim().startsWith("<html")) {
      return `API returned an HTML ${err.response.status} page. Check that the Incentra backend is running on the configured API URL.`;
    }
    return data;
  }
  if (data?.error) return data.error;
  if (data?.message) return data.message;
  if (data?.detail) return data.detail;
  if (typeof data === "object" && data) {
    const flat = Object.values(data).flat().join(", ");
    if (flat) return flat;
  }
  return fallback;
}

export { apiHost, apiBaseURL };
export default api;
