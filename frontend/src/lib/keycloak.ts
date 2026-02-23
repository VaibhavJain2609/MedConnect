import Keycloak from "keycloak-js";

// Single global instance
const keycloak = new Keycloak({
  url: process.env.NEXT_PUBLIC_KEYCLOAK_URL || "http://localhost:8080",
  realm: process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "medconnect",
  clientId: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "medconnect-frontend",
});

export default keycloak;
