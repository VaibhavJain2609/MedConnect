import { test, expect } from "./fixtures/auth";

/**
 * Patient portal journey — @auth.
 *
 * Runs as the generic E2E test user (E2E_TEST_EMAIL / E2E_TEST_PASSWORD),
 * which must be a *patient* account. `loginAs` mints a real token via
 * Keycloak direct grant and injects it before app boot — the test skips
 * when those env vars are unset.
 *
 * The appointments test additionally expects seeded demo data (`make
 * seed`): each seeded patient has ≥1 appointment with Dr. Priya Sharma or
 * Dr. Arjun Mehta. The queue/medications tests only assert the pages load
 * and render their expected states, so they pass with or without seed.
 */

test.describe("patient journey", { tag: "@auth" }, () => {
  test.beforeEach(async ({ loginAs }) => {
    await loginAs("patient");
  });

  test("appointments page lists the patient's appointments", async ({
    page,
  }) => {
    await page.goto("/patient/appointments");

    await expect(
      page.getByRole("heading", { name: "My Appointments" })
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByRole("button", { name: /book appointment/i })
    ).toBeVisible();

    // Appointment cards render the doctor's name. The default tab is
    // "Upcoming" — seeded appointments are morning slots, so as the day
    // progresses they all migrate to "Past". Wait for the query to settle
    // (card or empty state), then check whichever tab has entries.
    const doctorName = page.getByText(/dr\. (priya sharma|arjun mehta)/i);
    await expect(
      doctorName.first().or(page.getByText("No upcoming appointments"))
    ).toBeVisible();

    if (!(await doctorName.first().isVisible())) {
      await page.getByRole("button", { name: /^past \(/i }).click();
    }
    await expect(
      doctorName.first(),
      "no seeded appointments visible — is the E2E user a seeded patient? " +
        "run `make seed` and map its Keycloak sub (docs/seed.md)"
    ).toBeVisible();
  });

  test("live queue position page loads", async ({ page }) => {
    await page.goto("/patient/queue");

    await expect(
      page.getByRole("heading", { name: "Queue Status" })
    ).toBeVisible({ timeout: 30_000 });

    // Exactly one of these states renders: the not-checked-in empty state
    // (e.g. seeded Rohan) or the live position card (e.g. seeded Kabir is
    // "waiting", Ananya is "in consultation").
    await expect(
      page.getByText(
        /you're not checked in anywhere today|your position in queue|you're being seen now|your visit is complete|this queue entry was cancelled/i
      )
    ).toBeVisible();
  });

  test("medications page loads", async ({ page }) => {
    await page.goto("/patient/medications");

    await expect(
      page.getByRole("heading", { name: "Medications", exact: true })
    ).toBeVisible({ timeout: 30_000 });

    // Seeded patients have no prescriptions → the empty state; a patient
    // with real prescriptions gets the "Active now" section instead.
    await expect(
      page.getByText(/no medications found|no active medications|active now/i)
    ).toBeVisible();
  });
});
