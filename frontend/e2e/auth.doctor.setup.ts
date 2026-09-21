import { test as setup } from "@playwright/test";
import { doctorAuthFile } from "./auth-file";
import { loginViaKeycloak } from "./auth-helpers";

/**
 * Doctor auth setup — same flow as auth.setup.ts but for the doctor-portal
 * test account (E2E_DOCTOR_EMAIL / E2E_DOCTOR_PASSWORD). The session lands
 * in `e2e/.auth/doctor.json`; doctor specs reuse it via
 * `test.use({ storageState: doctorAuthFile })`.
 *
 * Skipped unless E2E_DOCTOR_EMAIL and E2E_DOCTOR_PASSWORD are set.
 *
 * To exercise seeded data (queue entries, clinic membership), point these
 * at a Keycloak user whose sub maps to a seeded doctor — e.g.
 * dr.priya@medconnect.demo. Run `make seed` first and create the matching
 * Keycloak users per docs/seed.md.
 */

setup.skip(
  !process.env.E2E_DOCTOR_EMAIL || !process.env.E2E_DOCTOR_PASSWORD,
  "E2E_DOCTOR_EMAIL / E2E_DOCTOR_PASSWORD not set — skipping doctor setup"
);

setup("authenticate doctor via Keycloak", async ({ page }) => {
  await loginViaKeycloak(
    page,
    process.env.E2E_DOCTOR_EMAIL!,
    process.env.E2E_DOCTOR_PASSWORD!,
    // Fail fast when the account isn't a doctor — /auth/callback routes
    // doctors to /doctor/dashboard.
    /\/doctor(\/|$)/
  );

  await page.context().storageState({ path: doctorAuthFile });
});
