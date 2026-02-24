import Keycloak from "keycloak-js";

// Single global instance - only initialize on client side
let keycloak: Keycloak | null = null;

if (typeof window !== "undefined") {
  keycloak = new Keycloak({
    url: process.env.NEXT_PUBLIC_KEYCLOAK_URL || "http://localhost:8080",
    realm: process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "medconnect",
    clientId: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "medconnect-frontend",
  });
}

export default keycloak as Keycloak;
