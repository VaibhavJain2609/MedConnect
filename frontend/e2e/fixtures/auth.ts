import {
  test as base,
  expect,
  type BrowserContext,
} from "@playwright/test";

/**
 * Shared auth fixture — real tokens via Keycloak direct grant (ROPC).
 *
 * Instead of driving the hosted Keycloak login UI, `loginAs(role)` POSTs
 * `grant_type=password` to the realm's token endpoint and injects the
 * resulting access + refresh tokens into the page via `addInitScript`
 * (localStorage keys below, read by `initKeycloak()` in
 * src/lib/auth.ts and handed to `keycloak.init()`).
 *
 * Nothing is mocked: the backend validates the real JWT against the
 * realm's JWKS, auto-provisioning/role sync run normally, and token
 * refresh hits the real token endpoint.
 *
 * Requirements:
 *   - a reachable Keycloak (E2E_KEYCLOAK_URL, default
 *     http://localhost:8080) with Direct Access Grants enabled on the
 *     frontend client — the bundled dev realm (keycloak/realm-export.json)
 *     has it enabled
 *   - credentials in the role's env-var pair (see ROLE_ENV below); the
 *     seeded demo users (`make seed` + the realm's imported demo users,
 *     password "demo-password") work out of the box — docs/seed.md
 *
 * Tests that call `loginAs` skip themselves when the role's credentials
 * are unset, so the suite degrades cleanly on environments without
 * Keycloak test accounts. Specs that need auth should also carry the
 * `@auth` tag so they can be excluded wholesale with
 * `--grep-invert @auth`.
 */

export type PortalRole = "patient" | "doctor" | "admin";

// localStorage keys read by initKeycloak() in src/lib/auth.ts — keep in
// sync (they're duplicated rather than imported so this file never pulls
// the app's keycloak-js dependency into the Node-side test process).
const E2E_ACCESS_TOKEN_KEY = "medconnect:e2e:keycloak-token";
const E2E_REFRESH_TOKEN_KEY = "medconnect:e2e:keycloak-refresh-token";

const ROLE_ENV: Record<PortalRole, [emailEnv: string, passwordEnv: string]> = {
  patient: ["E2E_TEST_EMAIL", "E2E_TEST_PASSWORD"],
  doctor: ["E2E_DOCTOR_EMAIL", "E2E_DOCTOR_PASSWORD"],
  admin: ["E2E_ADMIN_EMAIL", "E2E_ADMIN_PASSWORD"],
};

const keycloakUrl = () =>
  process.env.E2E_KEYCLOAK_URL || "http://localhost:8080";
const keycloakRealm = () => process.env.E2E_KEYCLOAK_REALM || "medconnect";
const keycloakClientId = () =>
  process.env.E2E_KEYCLOAK_CLIENT_ID || "medconnect-frontend";

export interface KeycloakTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

/**
 * Mint a real access/refresh token pair for `email` via the realm's
 * direct-grant (Resource Owner Password Credentials) endpoint.
 *
 * The client_id must be `medconnect-frontend` (the same client the app
 * uses) so the refresh token stays bound to the client keycloak-js will
 * use for `updateToken()` — and so the backend's audience check
 * (`medconnect-backend`, added by the client's audience protocol mapper)
 * passes.
 */
export async function mintTokens(
  email: string,
  password: string
): Promise<KeycloakTokens> {
  const url = `${keycloakUrl()}/realms/${keycloakRealm()}/protocol/openid-connect/token`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "password",
      client_id: keycloakClientId(),
      username: email,
      password,
      scope: "openid",
    }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `Keycloak direct grant failed for ${email}: HTTP ${res.status} ` +
        `${body}\nToken endpoint: ${url}\nCheck that Keycloak is running, ` +
        `the user exists (seeded demo users ship with the realm import — ` +
        `password "demo-password", see docs/seed.md), and Direct Access ` +
        `Grants is enabled on the ${keycloakClientId()} client.`
    );
  }
  const json = (await res.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  };
  return {
    accessToken: json.access_token,
    refreshToken: json.refresh_token,
    expiresIn: json.expires_in,
  };
}

/**
 * Write the tokens into localStorage before any app script runs.
 * `initKeycloak()` picks them up and passes them to `keycloak.init()`.
 */
async function injectTokens(
  context: BrowserContext,
  tokens: KeycloakTokens
): Promise<void> {
  await context.addInitScript(
    ([accessToken, refreshToken]) => {
      window.localStorage.setItem(
        "medconnect:e2e:keycloak-token",
        accessToken
      );
      window.localStorage.setItem(
        "medconnect:e2e:keycloak-refresh-token",
        refreshToken
      );
    },
    [tokens.accessToken, tokens.refreshToken]
  );
}

export const test = base.extend<{
  /**
   * Authenticate the test's browser context as the given portal role.
   * Call in `test.beforeEach` (before `page.goto`). Skips the test when
   * the role's credential env vars are unset.
   */
  loginAs: (role: PortalRole) => Promise<void>;
}>({
  loginAs: async ({ context }, use) => {
    await use(async (role) => {
      const [emailEnv, passwordEnv] = ROLE_ENV[role];
      const email = process.env[emailEnv];
      const password = process.env[passwordEnv];
      test.skip(
        !email || !password,
        `Set ${emailEnv} and ${passwordEnv} to run ${role} e2e tests (see docs/e2e.md)`
      );
      const tokens = await mintTokens(email!, password!);
      await injectTokens(context, tokens);
    });
  },
});

export { expect };
