import keycloak from "./keycloak";
import { getMe as fetchMe, type UserProfile } from "./api/users";
import { useAuthStore } from "@/stores/auth-store";
import { useClinicStore } from "@/stores/clinic-store";

export interface User {
  id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  role: "patient" | "doctor" | "admin";
  language_pref: string;
  photo_url?: string | null;
}

let initialized = false;
let initPromise: Promise<boolean> | null = null;

export async function initKeycloak(): Promise<boolean> {
  if (typeof window === "undefined") return false;

  // Already initialized — just return current state
  if (initialized) {
    return !!keycloak?.authenticated;
  }

  // In-flight — return the same promise to avoid double-init
  if (initPromise) {
    return initPromise;
  }

  if (!keycloak) return false;

  initPromise = (async () => {
  try {
    const authenticated = await keycloak!.init({
      onLoad: "check-sso",
      pkceMethod: "S256",
      checkLoginIframe: false,
      silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
      redirectUri: window.location.origin + "/auth/callback",
    });

    initialized = true;

    if (authenticated && keycloak!.token) {
      // Set up auto-refresh
      keycloak!.onTokenExpired = () => {
        keycloak!.updateToken(30).catch(() => {
          console.warn("Token refresh failed");
        });
      };
    }

    return authenticated;
  } catch (error) {
    console.error("Keycloak init error:", error);
    initialized = true;
    return false;
  } finally {
    initPromise = null;
  }
  })();

  return initPromise;
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

// Registered by Providers so logout() can purge cached server data.
let _queryClient: { clear: () => void } | null = null;
export function registerQueryClient(client: { clear: () => void } | null) {
  _queryClient = client;
}

export function logout() {
  if (typeof window === "undefined") return;

  // Drop React Query cache — PHI must not persist on shared devices
  try {
    _queryClient?.clear();
  } catch {
    // ignore
  }

  // Clear persisted client state
  try {
    useAuthStore.getState().clear();
    useClinicStore.getState().clearClinics();
    localStorage.removeItem("clinic-store");
    localStorage.removeItem("auth-store");
  } catch {
    // ignore storage errors (private mode, etc.)
  }

  // Clear service-worker caches
  try {
    if ("caches" in window) {
      void caches
        .keys()
        .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
        .catch(() => {});
    }
  } catch {
    // ignore
  }

  if (keycloak) {
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
  return await fetchMe();
}
