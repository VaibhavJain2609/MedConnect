import { test, expect } from "@playwright/test";
import { adminAuthFile } from "./auth-file";

/**
 * Admin portal e2e — SKIPPED BY DEFAULT.
 *
 * Runs as the admin test account (E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD);
 * auth.admin.setup.ts writes the session to e2e/.auth/admin.json first.
 *
 * The dashboard KPI assertions pass against any database — but pair them
 * with `make seed` + a Keycloak user mapped to admin@medconnect.demo (see
 * docs/seed.md) for meaningful counts.
 */

test.skip(
  !process.env.E2E_ADMIN_EMAIL || !process.env.E2E_ADMIN_PASSWORD,
  "Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to run admin e2e tests"
);

// Every test in this file starts already logged in as the E2E admin user.
test.use({ storageState: adminAuthFile });

test.describe("admin portal", () => {
  test("dashboard shows KPI stat cards", async ({ page }) => {
    await page.goto("/admin/dashboard");

    await expect(
      page.getByRole("heading", { name: "Dashboard", exact: true })
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByText("Overview of your healthcare platform")
    ).toBeVisible();

    // The four StatCard titles from the platform stats endpoint.
    for (const title of [
      "Total Patients",
      "Medical Records",
      "Total Doctors",
      "Prescriptions",
    ]) {
      await expect(page.getByText(title, { exact: true })).toBeVisible();
    }

    // Date-range filter drives the KPI queries.
    await expect(
      page.getByRole("combobox")
    ).toBeVisible();
  });

  test("system page renders dependency health cards", async ({ page }) => {
    await page.goto("/admin/system");

    await expect(
      page.getByRole("heading", { name: "System Health" })
    ).toBeVisible({ timeout: 30_000 });

    // One banner always renders — green, red, or amber depending on probe
    // results — so assert the set rather than a healthy outcome.
    await expect(
      page.getByText(
        /all systems operational|one or more dependencies are down|status unknown/i
      )
    ).toBeVisible();

    // DependencyCard titles (exact match avoids the banner's "API v…" text).
    for (const dep of ["API", "PostgreSQL", "Medicine DB", "Redis"]) {
      await expect(page.getByText(dep, { exact: true })).toBeVisible();
    }

    // Aggregate counts from the admin diagnostics endpoint.
    await expect(
      page.getByText("Total Users", { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText("Appointments Today", { exact: true })
    ).toBeVisible();
  });

  test("notifications broadcast form renders and confirms before send", async ({
    page,
  }) => {
    await page.goto("/admin/notifications");

    await expect(
      page.getByRole("heading", { name: "Notifications", exact: true })
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByRole("heading", { name: "New announcement" })
    ).toBeVisible();

    // Audience radio group.
    for (const audience of ["All users", "Patients", "Doctors", "Admins"]) {
      await expect(
        page.getByRole("radio", { name: audience })
      ).toBeVisible();
    }

    // Live recipient count for the selected audience.
    await expect(
      page.getByText(/will be sent to|counting recipients/i)
    ).toBeVisible();

    // Title / type / message fields.
    await expect(
      page.getByPlaceholder(/scheduled maintenance/i)
    ).toBeVisible();
    await expect(page.getByRole("combobox")).toBeVisible();
    await expect(
      page.getByPlaceholder(/write the announcement/i)
    ).toBeVisible();

    // Fill the form and submit — the destructive action is gated behind a
    // confirm dialog. Cancel out of it; never actually broadcast.
    await page
      .getByPlaceholder(/scheduled maintenance/i)
      .fill("E2E smoke announcement");
    await page
      .getByPlaceholder(/write the announcement/i)
      .fill("Sent by the Playwright e2e suite — cancelled before send.");
    await page
      .getByRole("button", { name: /send announcement/i })
      .click();

    const dialog = page.getByRole("alertdialog");
    await expect(
      dialog.getByText("Send this announcement?")
    ).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).not.toBeVisible();
  });
});
