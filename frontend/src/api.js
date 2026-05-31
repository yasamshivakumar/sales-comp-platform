import axios from "axios";

// ============================================================================
// API CONFIGURATION
// ============================================================================
// Build API base URL from environment variables
const protocol = process.env.NODE_ENV === 'production' ? 'https' : 'http';
const apiHost = process.env.REACT_APP_API_HOST || 'http://localhost:8000';
const apiBaseURL = process.env.REACT_APP_API_BASE_URL || `${apiHost}/api`;

// ============================================================================
// DEBUG LOGGING (only in development)
// ============================================================================
const isDevelopment = process.env.NODE_ENV !== 'production';
const isDebugEnabled = process.env.REACT_APP_DEBUG === 'true';

if (isDevelopment && isDebugEnabled) {
  console.log('[API] Configured base URL:', apiBaseURL);
}

// ============================================================================
// CREATE AXIOS INSTANCE
// ============================================================================
const api = axios.create({
  baseURL: apiBaseURL,
  timeout: parseInt(process.env.REACT_APP_REQUEST_TIMEOUT_MS || '30000', 10),
});

// ============================================================================
// REQUEST INTERCEPTOR - Add authentication token
// ============================================================================
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");

  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }

  return config;
});

// ============================================================================
// RESPONSE INTERCEPTOR - Handle errors and logging
// ============================================================================
api.interceptors.response.use(
  (response) => {
    if (isDevelopment && isDebugEnabled) {
      console.log('[API] Response:', response.status, response.config.url);
    }
    return response;
  },
  (error) => {
    // Handle 401 Unauthorized - redirect to login
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("username");
      // Optional: Emit event or redirect to login
      window.dispatchEvent(new CustomEvent('unauthorized'));
    }

    if (isDevelopment && isDebugEnabled) {
      console.error('[API] Error:', error.response?.status, error.message);
    }

    return Promise.reject(error);
  }
);

export default api;