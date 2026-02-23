import type Keycloak from "keycloak-js";

let keycloak: Keycloak | null = null;

export async function getKeycloak(): Promise<Keycloak> {
  if (!keycloak) {
    const KeycloakConstructor = (await import("keycloak-js")).default;
    keycloak = new KeycloakConstructor({
      url: process.env.NEXT_PUBLIC_KEYCLOAK_URL || "http://localhost:8080",
      realm: process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "medconnect",
      clientId:
        process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "medconnect-frontend",
    });
  }
  return keycloak;
}
