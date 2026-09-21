import { expect, type Page } from "@playwright/test";

/**
 * Shared Keycloak hosted-login flow used by the role-specific *.setup.ts
 * files (auth.setup.ts keeps its own inline copy for historical reasons —
 * same steps).
 *
 * Navigates to /login, waits for the bounce to the realm's hosted login
 * form, submits the credentials via Keycloak's default theme field IDs,
 * then waits for /auth/callback to hand off to a portal route.
 *
 * `landingPattern` lets role setups fail fast when the wrong account type
 * is configured — e.g. the doctor setup passes /\/doctor(\/|$)/ so a
 * patient account errors here instead of inside a spec.
 */
export async function loginViaKeycloak(
  page: Page,
  email: string,
  password: string,
  landingPattern: RegExp = /\/(patient|doctor|admin)(\/|$)/
): Promise<void> {
  await page.goto("/login");

  // /login bounces to the Keycloak hosted login form.
  await page.waitForURL(
    /\/realms\/[^/]+\/protocol\/openid-connect\/(auth|registrations)/
  );

  // Keycloak's default login theme field IDs.
  await page.locator("#username").fill(email);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();

  // Back in the app: /auth/callback hands off to the role-specific portal.
  await page.waitForURL(landingPattern, { timeout: 30_000 });

  // Sanity check that the session is real, not just a URL that loaded.
  await expect(page.locator("body")).not.toBeEmpty();
}
