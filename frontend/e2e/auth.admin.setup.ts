import { test as setup } from "@playwright/test";
import { adminAuthFile } from "./auth-file";
import { loginViaKeycloak } from "./auth-helpers";

/**
 * Admin auth setup — same flow as auth.setup.ts but for the admin-portal
 * test account (E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD). The session lands
 * in `e2e/.auth/admin.json`; admin specs reuse it via
 * `test.use({ storageState: adminAuthFile })`.
 *
 * Skipped unless E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD are set.
 *
 * To line up with the seeded demo dataset, point these at a Keycloak user
 * whose sub maps to admin@medconnect.demo (see `make seed` + docs/seed.md).
 */

setup.skip(
  !process.env.E2E_ADMIN_EMAIL || !process.env.E2E_ADMIN_PASSWORD,
  "E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD not set — skipping admin setup"
);

setup("authenticate admin via Keycloak", async ({ page }) => {
  await loginViaKeycloak(
    page,
    process.env.E2E_ADMIN_EMAIL!,
    process.env.E2E_ADMIN_PASSWORD!,
    // Fail fast when the account isn't an admin — /auth/callback routes
    // admins to /admin/dashboard.
    /\/admin(\/|$)/
  );

  await page.context().storageState({ path: adminAuthFile });
});
