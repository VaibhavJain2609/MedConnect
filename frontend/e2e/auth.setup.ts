import { test as setup, expect } from "@playwright/test";
import { authFile } from "./auth-file";

/**
 * Auth setup — logs in through the real Keycloak hosted login page once and
 * saves the resulting storage state (cookies + localStorage, including the
 * Keycloak tokens) to `e2e/.auth/user.json`. Authenticated specs reuse that
 * file via `test.use({ storageState: authFile })` so they never touch the
 * login UI themselves.
 *
 * Skipped unless E2E_TEST_EMAIL and E2E_TEST_PASSWORD are set — without
 * credentials there is no way through Keycloak and nothing to save.
 *
 * The test user must already exist in the realm pointed at by
 * NEXT_PUBLIC_KEYCLOAK_* and should have a patient role (adjust the landing
 * URL assertion below if you point this at a doctor/admin account).
 */
setup.skip(
  !process.env.E2E_TEST_EMAIL || !process.env.E2E_TEST_PASSWORD,
  "E2E_TEST_EMAIL / E2E_TEST_PASSWORD not set — skipping authenticated setup"
);

setup("authenticate via Keycloak", async ({ page }) => {
  await page.goto("/login");

  // /login bounces to the Keycloak hosted login form.
  await page.waitForURL(
    /\/realms\/[^/]+\/protocol\/openid-connect\/(auth|registrations)/
  );

  // Keycloak's default login theme field IDs.
  await page.locator("#username").fill(process.env.E2E_TEST_EMAIL!);
  await page.locator("#password").fill(process.env.E2E_TEST_PASSWORD!);
  await page.locator("#kc-login").click();

  // Back in the app: /auth/callback hands off to the role-specific portal.
  // Wait until we've landed on a portal route rather than asserting an
  // exact path — the destination depends on the test user's role.
  await page.waitForURL(/\/(patient|doctor|admin)(\/|$)/, {
    timeout: 30_000,
  });

  // Sanity check that the session is real, not just a URL that loaded.
  await expect(page.locator("body")).not.toBeEmpty();

  await page.context().storageState({ path: authFile });
});
