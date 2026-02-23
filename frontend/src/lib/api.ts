import axios from "axios";
import { getKeycloak } from "./keycloak";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(async (config) => {
  if (typeof window === "undefined") return config;
  const keycloak = await getKeycloak();
  if (keycloak.authenticated) {
    try {
      await keycloak.updateToken(30);
    } catch {
      // Token refresh failed, will get 401
    }
    config.headers.Authorization = `Bearer ${keycloak.token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Don't auto-redirect on 401 — let the caller handle it
    // This prevents redirect loops during initAuth
    return Promise.reject(error);
  }
);

export default api;
