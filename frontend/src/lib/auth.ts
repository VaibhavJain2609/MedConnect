import keycloak from "./keycloak";
import api from "./api";

export interface User {
  id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  role: "patient" | "doctor" | "admin";
  language_pref: string;
}

let initialized = false;

export async function initKeycloak(): Promise<boolean> {
  if (typeof window === "undefined") return false;

  // Already initialized — just return current state
  if (initialized) {
    return !!keycloak.authenticated;
  }

  try {
    const authenticated = await keycloak.init({
      onLoad: "check-sso",
      pkceMethod: "S256",
      checkLoginIframe: false,
      redirectUri: window.location.origin + "/auth/callback",
    });

    initialized = true;

    console.log("Keycloak init done:", {
      authenticated,
      hasToken: !!keycloak.token,
      hasRefreshToken: !!keycloak.refreshToken,
      hasIdToken: !!keycloak.idToken,
    });

    if (authenticated && keycloak.token) {
      // Set up auto-refresh
      keycloak.onTokenExpired = () => {
        keycloak.updateToken(30).catch(() => {
          console.warn("Token refresh failed");
        });
      };
    }

    return authenticated;
  } catch (error) {
    console.error("Keycloak init error:", error);
    initialized = true;
    return false;
  }
}

export function loginRedirect() {
  if (typeof window !== "undefined" && keycloak) {
    keycloak.login({ redirectUri: window.location.origin + "/auth/callback" });
  }
}

export function signupRedirect() {
  if (typeof window !== "undefined" && keycloak) {
    keycloak.register({ redirectUri: window.location.origin + "/auth/callback" });
  }
}

export function logout() {
  if (typeof window !== "undefined" && keycloak) {
    keycloak.logout({ redirectUri: window.location.origin });
  }
}

export function getAccessToken(): string | undefined {
  return keycloak?.token;
}

export function isAuthenticated(): boolean {
  return !!keycloak?.authenticated;
}

export async function getMe(): Promise<User> {
  const res = await api.get("/api/v1/auth/me");
  return res.data;
}
