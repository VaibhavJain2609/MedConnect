import axios from "axios";
import keycloak from "./keycloak";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(async (config) => {
  if (typeof window === "undefined") return config;

  if (keycloak.authenticated && keycloak.token) {
    try {
      await keycloak.updateToken(30);
    } catch (error) {
      console.warn("Token refresh failed:", error);
    }
    config.headers.Authorization = `Bearer ${keycloak.token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    return Promise.reject(error);
  }
);

export default api;
