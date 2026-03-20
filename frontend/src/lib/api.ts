import axios from "axios";
import keycloak from "./keycloak";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(async (config) => {
  if (typeof window === "undefined") return config;

  if (keycloak && keycloak.authenticated && keycloak.token) {
    try {
      await keycloak.updateToken(30);
    } catch (error) {
      console.warn("Token refresh failed:", error);
    }
    config.headers.Authorization = `Bearer ${keycloak.token}`;
  }

  // Attach active clinic ID for clinic-scoped endpoints
  try {
    const raw = localStorage.getItem("clinic-store");
    if (raw) {
      const parsed = JSON.parse(raw);
      const clinicId = parsed?.state?.activeClinicId;
      if (clinicId) {
        config.headers["X-Clinic-Id"] = clinicId;
      }
    }
  } catch {
    // ignore localStorage errors (SSR, private mode, etc.)
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Enhanced error handling
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;

      // Handle 401 Unauthorized
      if (status === 401) {
        console.warn("Unauthorized access - redirecting to login");
        if (typeof window !== "undefined") {
          const path = window.location.pathname;
          const isAuthPage =
            path.startsWith("/auth/") ||
            path.startsWith("/login") ||
            path === "/";
          if (!isAuthPage && keycloak) {
            keycloak.login({ redirectUri: window.location.origin + "/auth/callback" });
          }
        }
      }

      // Handle 403 Forbidden
      if (status === 403) {
        console.error("Access forbidden - insufficient permissions");
        error.userMessage = "You don't have permission to perform this action";
      }

      // Handle 404 Not Found
      if (status === 404) {
        error.userMessage = "The requested resource was not found";
      }

      // Handle 500 Server Error
      if (status >= 500) {
        error.userMessage = "Server error. Please try again later";
      }

      // Extract error message from backend
      if (data?.detail) {
        if (typeof data.detail === "string") {
          error.userMessage = data.detail;
        } else if (data.detail.message) {
          error.userMessage = data.detail.message;
        }
      } else if (data?.error?.message) {
        error.userMessage = data.error.message;
      }
    } else if (error.request) {
      // Request made but no response received
      error.userMessage = "Network error. Please check your connection";
    } else {
      // Something else happened
      error.userMessage = error.message || "An unexpected error occurred";
    }

    return Promise.reject(error);
  }
);

export default api;
