import { test, expect } from "@playwright/test";
import { authFile } from "./auth-file";

/**
 * Authenticated appointments template — SKIPPED BY DEFAULT.
 *
 * This whole file is skipped unless E2E_TEST_EMAIL and E2E_TEST_PASSWORD are
 * set. When they are, the `setup` project (auth.setup.ts) runs first, writes
 * `e2e/.auth/user.json`, and every test here starts with that session
 * already loaded — no per-test login.
 *
 * To enable:
 *   E2E_TEST_EMAIL=patient@example.com \
 *   E2E_TEST_PASSWORD=secret \
 *   npm run test:e2e -- appointments.spec.ts
 *
 * When adding real tests, replace the placeholder below and target stable
 * selectors (role/label/text). Prefer adding `data-testid` attributes to
 * components over coupling to Tailwind classes.
 */

test.skip(
  !process.env.E2E_TEST_EMAIL || !process.env.E2E_TEST_PASSWORD,
  "Set E2E_TEST_EMAIL and E2E_TEST_PASSWORD to run authenticated e2e tests"
);

// Every test in this file starts already logged in as the E2E test user.
test.use({ storageState: authFile });

test.describe("patient appointments", () => {
  test("appointments page loads for the test user", async ({ page }) => {
    // Assumes the E2E test account has the patient role — change the route
    // (e.g. /doctor/appointments) if pointing at a doctor account.
    await page.goto("/patient/appointments");
    await expect(page).toHaveURL(/\/patient\/appointments/);

    // TODO: replace with real assertions once test data seeding exists —
    // e.g. await expect(page.getByRole('heading', { name: /appointments/i })).toBeVisible();
  });
});
