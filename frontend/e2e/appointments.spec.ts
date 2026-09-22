import { test, expect } from "./fixtures/auth";

/**
 * Authenticated appointments template — @auth.
 *
 * `loginAs("patient")` mints a real Keycloak token via direct grant and
 * injects it before app boot (see fixtures/auth.ts). The test skips
 * itself unless E2E_TEST_EMAIL and E2E_TEST_PASSWORD are set — in CI the
 * seeded demo users (docs/seed.md, password "demo-password") are wired
 * up by the workflow.
 *
 * To run locally:
 *   make seed
 *   E2E_TEST_EMAIL=kabir.singh@medconnect.demo \
 *   E2E_TEST_PASSWORD=demo-password \
 *   npm run test:e2e -- appointments.spec.ts
 *
 * When adding real tests, replace the placeholder below and target stable
 * selectors (role/label/text). Prefer adding `data-testid` attributes to
 * components over coupling to Tailwind classes.
 */

test.describe("patient appointments", { tag: "@auth" }, () => {
  test.beforeEach(async ({ loginAs }) => {
    await loginAs("patient");
  });

  test("appointments page loads for the test user", async ({ page }) => {
    // Assumes the E2E test account has the patient role — change the route
    // (e.g. /doctor/appointments) if pointing at a doctor account.
    await page.goto("/patient/appointments");
    await expect(page).toHaveURL(/\/patient\/appointments/);

    // TODO: replace with real assertions once test data seeding exists —
    // e.g. await expect(page.getByRole('heading', { name: /appointments/i })).toBeVisible();
  });
});
