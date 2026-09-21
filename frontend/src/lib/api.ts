import axios from "axios";
import keycloak from "./keycloak";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// MD-394: Single shared promise so concurrent requests don't each trigger a token refresh
let _tokenRefreshPromise: Promise<void> | null = null;

api.interceptors.request.use(async (config) => {
  if (typeof window === "undefined") return config;

  if (keycloak && keycloak.authenticated) {
    if (!_tokenRefreshPromise) {
      _tokenRefreshPromise = keycloak
        .updateToken(30)
        .then(() => {})
        .catch((err) => { console.warn("Token refresh failed:", err); })
        .finally(() => { _tokenRefreshPromise = null; });
    }
    await _tokenRefreshPromise;
    if (keycloak.token) {
      config.headers.Authorization = `Bearer ${keycloak.token}`;
    }
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
        // Report server-side failures to Sentry. 4xx is intentionally not
        // captured — expected client errors would just be noise. Dynamic
        // import keeps @sentry/nextjs out of the initial bundle and makes
        // this a no-op when the DSN isn't configured.
        if (typeof window !== "undefined" && process.env.NEXT_PUBLIC_SENTRY_DSN) {
          import("@sentry/nextjs")
            .then((Sentry) => Sentry.captureException(error))
            .catch(() => {});
        }
      }

      // Extract error message from backend error envelope.
      // FastAPI handlers wrap errors as detail: { error: { code, message } }.
      const backendMessage =
        data?.detail?.error?.message ??
        data?.error?.message ??
        (typeof data?.detail === "string" ? data.detail : undefined) ??
        (typeof data?.detail?.message === "string" ? data.detail.message : undefined);
      if (backendMessage) {
        error.userMessage = backendMessage;
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
