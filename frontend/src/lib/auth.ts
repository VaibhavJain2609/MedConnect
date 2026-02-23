import { getKeycloak } from "./keycloak";
import api from "./api";
import type Keycloak from "keycloak-js";

export interface User {
  id: string;
  email: string | null;
  phone: string | null;
  full_name: string;
  role: "patient" | "doctor" | "admin";
  language_pref: string;
}

let initialized = false;
let _keycloak: Keycloak | null = null;

export async function initKeycloak(): Promise<boolean> {
  _keycloak = await getKeycloak();
  if (initialized) return _keycloak.authenticated ?? false;

  const authenticated = await _keycloak.init({
    onLoad: "check-sso",
    silentCheckSsoRedirectUri:
      typeof window !== "undefined"
        ? `${window.location.origin}/silent-check-sso.html`
        : undefined,
    pkceMethod: "S256",
  });

  initialized = true;

  // Auto-refresh token before it expires
  _keycloak.onTokenExpired = () => {
    _keycloak!.updateToken(30).catch(() => {
      _keycloak!.login();
    });
  };

  return authenticated;
}

export async function loginRedirect() {
  const kc = await getKeycloak();
  kc.login();
}

export async function signupRedirect() {
  const kc = await getKeycloak();
  kc.register();
}

export async function logout() {
  const kc = await getKeycloak();
  kc.logout({ redirectUri: window.location.origin });
}

export async function getAccessToken(): Promise<string | undefined> {
  const kc = await getKeycloak();
  return kc.token;
}

export async function isAuthenticated(): Promise<boolean> {
  const kc = await getKeycloak();
  return !!kc.authenticated;
}

export async function getMe(): Promise<User> {
  const res = await api.get("/api/v1/auth/me");
  return res.data;
}
