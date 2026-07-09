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
const AUTH_STORAGE_KEYS = [
  "token",
  SESSION_EXPIRES_AT_KEY,
  "username",
  "email",
  "role",
  "user_id",
  "name",
];
let logoutTimer = null;

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

export function isSessionExpired() {
  const expiresAt = sessionExpiresAtMs();
  return Boolean(expiresAt && Date.now() >= expiresAt);
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
    clearAuthStorage();
    window.dispatchEvent(new CustomEvent("session-expired"));
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }, delay);
}

export function saveAuthSession(data) {
  clearLegacyLocalAuthStorage();
  sessionStorage.setItem("token", data.token);
  sessionStorage.setItem("email", data.email || "");
  sessionStorage.setItem("user_id", data.user_id || "");
  sessionStorage.setItem("role", data.role || "");
  sessionStorage.setItem("name", data.name || "");
  if (data.token_expires_at) {
    sessionStorage.setItem(SESSION_EXPIRES_AT_KEY, data.token_expires_at);
  } else {
    sessionStorage.removeItem(SESSION_EXPIRES_AT_KEY);
  }
  scheduleAutoLogout();
  window.dispatchEvent(new CustomEvent("auth-changed"));
}

export function getAuthToken() {
  return sessionStorage.getItem("token");
}

export function getAuthSessionValue(key) {
  return sessionStorage.getItem(key);
}

api.interceptors.request.use((config) => {
  if (isSessionExpired()) {
    clearAuthStorage();
    window.dispatchEvent(new CustomEvent("session-expired"));
    return Promise.reject(new Error("Session expired. Please sign in again."));
  }
  const token = getAuthToken();
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
    if (isDevelopment && isDebugEnabled) {
      console.log("[API] Response:", response.status, response.config.url);
    }
    return response;
  },
  (error) => {
    const requestUrl = error.config?.url || "";
    const isAuthRequest = /auth\/(email-login|oidc-exchange)\/?$/.test(requestUrl);

    if (error.response?.status === 401 && !isAuthRequest) {
      clearAuthStorage();
      window.dispatchEvent(new CustomEvent("unauthorized"));
      if (
        window.location.pathname !== "/login" &&
        !window.location.pathname.startsWith("/invite")
      ) {
        window.location.href = "/login";
      }
    }

    if (isDevelopment && isDebugEnabled) {
      console.error("[API] Error:", error.response?.status, error.message);
    }

    return Promise.reject(error);
  }
);

clearLegacyLocalAuthStorage();
scheduleAutoLogout();

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
