import axios from "axios";

// ============================================================================
// API CONFIGURATION (local dev vs Vercel → Render)
// ============================================================================
function normalizeBaseUrl(url) {
  if (!url) return "";
  return String(url).trim().replace(/\/+$/, "");
}

const apiHost = normalizeBaseUrl(
  process.env.REACT_APP_API_HOST || "http://localhost:8000"
);
const apiBaseURL =
  normalizeBaseUrl(process.env.REACT_APP_API_BASE_URL) ||
  `${apiHost}/api`;

const isDevelopment = process.env.NODE_ENV !== "production";
const isDebugEnabled = process.env.REACT_APP_DEBUG === "true";

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

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;
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
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("username");
      localStorage.removeItem("email");
      localStorage.removeItem("role");
      localStorage.removeItem("user_id");
      localStorage.removeItem("name");
      window.dispatchEvent(new CustomEvent("unauthorized"));
    }

    if (isDevelopment && isDebugEnabled) {
      console.error("[API] Error:", error.response?.status, error.message);
    }

    return Promise.reject(error);
  }
);

/** Human-readable hint when the browser blocks the request (CORS / wrong API URL). */
export function getApiErrorMessage(err, fallback = "Request failed") {
  if (!err.response) {
    return `Cannot reach API at ${apiBaseURL}. Check REACT_APP_API_BASE_URL on Vercel and CORS on Render.`;
  }
  const data = err.response.data;
  if (typeof data === "string") return data;
  if (data?.error) return data.error;
  if (data?.detail) return data.detail;
  if (typeof data === "object" && data) {
    const flat = Object.values(data).flat().join(", ");
    if (flat) return flat;
  }
  return fallback;
}

export { apiHost, apiBaseURL };
export default api;
