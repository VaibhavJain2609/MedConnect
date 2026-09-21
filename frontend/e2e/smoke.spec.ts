import { test, expect } from "@playwright/test";

/**
 * Public smoke tests — no credentials required.
 *
 * Only unauthenticated routes are exercised:
 *   /        → marketing landing page (shown once Keycloak init settles)
 *   /login   → client-side redirect to the Keycloak realm login endpoint
 *   /signup  → client-side redirect to the Keycloak registration endpoint
 *
 * Redirect assertions listen for the outgoing *request* to Keycloak rather
 * than waiting for the page URL to settle, so they hold even when Keycloak
 * itself is unreachable (connection refused / error page). When Keycloak
 * does respond — e.g. the docker compose stack is up — the login-form
 * check runs too.
 */

// Matches both the login (.../protocol/openid-connect/auth) and
// registration (.../protocol/openid-connect/registrations) endpoints.
const KEYCLOAK_AUTH_URL =
  /\/realms\/[^/]+\/protocol\/openid-connect\/(auth|registrations)/;

test.describe("public pages (unauthenticated)", () => {
  test("landing page renders marketing content", async ({ page }) => {
    await page.goto("/");

    // HomeClient renders a spinner until keycloak.init() resolves (or fails,
    // when Keycloak is down) — give it room before asserting.
    await expect(
      page.getByRole("heading", { name: /your health records/i })
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/one platform/i)).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^login$/i })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /sign up/i })
    ).toBeVisible();
  });

  test("/login redirects to the Keycloak realm", async ({ page }) => {
    // Arm the listener before navigating — keycloak.login() fires the
    // redirect as soon as the login page's useEffect runs.
    const redirect = page.waitForRequest(KEYCLOAK_AUTH_URL);
    await page.goto("/login");
    const request = await redirect;
    expect(request.url()).toContain("openid-connect");

    // If Keycloak is actually reachable, the hosted login form renders —
    // verify it as a stronger signal, but don't require it.
    const authResponse = await page
      .waitForResponse(
        (res) => KEYCLOAK_AUTH_URL.test(res.url()) && res.ok(),
        { timeout: 10_000 }
      )
      .catch(() => null);
    if (authResponse) {
      await expect(page.locator("#username")).toBeVisible();
      await expect(page.locator("#password")).toBeVisible();
    }
  });

  test("/signup redirects to Keycloak registration", async ({ page }) => {
    const redirect = page.waitForRequest(KEYCLOAK_AUTH_URL);
    await page.goto("/signup");
    const request = await redirect;
    // keycloak.register() targets the registrations endpoint specifically.
    expect(request.url()).toContain("openid-connect/registrations");
  });
});
