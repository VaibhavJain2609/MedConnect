import { type Request } from "@playwright/test";
import { test, expect } from "./fixtures/auth";

/**
 * Doctor queue e2e — @auth, and REQUIRES seeded demo data.
 *
 * Prerequisites:
 *   1. `make seed` — creates the demo clinic, doctors, patients, and two
 *      queue entries for "today" (see backend/scripts/seed_demo_data.py):
 *        - Ananya Iyer  — in_consultation
 *        - Kabir Singh  — waiting
 *      Rohan Verma (the third seeded patient) is deliberately NOT in the
 *      queue so the check-in test can add him.
 *   2. A doctor account in Keycloak whose sub maps to a seeded doctor.
 *      Set E2E_DOCTOR_EMAIL / E2E_DOCTOR_PASSWORD — the realm's imported
 *      demo users work as-is: dr.priya@medconnect.demo / demo-password
 *      (docs/seed.md).
 *
 * Check-in has no UI yet (the queue page is read/operate-only), so the
 * check-in test drives POST /api/v1/queue directly through page.request,
 * reusing the Authorization + X-Clinic-Id headers captured from the app's
 * own GET /api/v1/queue call. This also makes the API base URL immune to
 * environment differences — it's whatever origin the app actually used.
 */

/** Extract the API origin + auth/clinic headers the app itself used. */
async function captureApiContext(request: Request) {
  const headers = await request.headers();
  return {
    apiOrigin: new URL(request.url()).origin,
    authorization: headers["authorization"] ?? "",
    clinicId: headers["x-clinic-id"] ?? "",
  };
}

test.describe("doctor queue", { tag: "@auth" }, () => {
  test.beforeEach(async ({ loginAs }) => {
    await loginAs("doctor");
  });

  test("today's queue shows the seeded patients", async ({ page }) => {
    await page.goto("/doctor/queue");

    await expect(
      page.getByRole("heading", { name: "Queue", exact: true })
    ).toBeVisible({ timeout: 30_000 });

    // Seeded entries: Ananya is mid-consult, Kabir is still waiting.
    const inConsultSection = page.locator("section", {
      has: page.getByRole("heading", { name: "In Consultation" }),
    });
    await expect(inConsultSection.getByText("Ananya Iyer")).toBeVisible();

    const waitingSection = page.locator("section", {
      has: page.getByRole("heading", { name: /waiting/i }),
    });
    await expect(waitingSection.getByText("Kabir Singh")).toBeVisible();
  });

  test("check a patient in → appears in list → advance status", async ({
    page,
  }) => {
    // Arm the request listener before navigating — the page fires
    // GET /api/v1/queue as soon as the clinic store resolves.
    const queueRequest = page.waitForRequest(
      (req) => req.url().includes("/api/v1/queue") && req.method() === "GET"
    );
    await page.goto("/doctor/queue");

    const captured = await queueRequest.catch(() => {
      throw new Error(
        "App never called GET /api/v1/queue — the doctor likely has no " +
          "active clinic. Seed a clinic membership first (`make seed`)."
      );
    });
    const { apiOrigin, authorization, clinicId } = await captureApiContext(
      captured
    );
    expect(authorization, "no Authorization header on queue request").toBeTruthy();
    expect(clinicId, "no X-Clinic-Id header on queue request").toBeTruthy();

    const authHeaders = { authorization, "x-clinic-id": clinicId };

    // Resolve the seeded patient not already in today's queue (Rohan Verma)
    // via the doctor patient-search endpoint.
    const search = await page.request.get(
      `${apiOrigin}/api/v1/doctors/patients/search`,
      { headers: authHeaders, params: { q: "rohan" } }
    );
    expect(search.ok(), "patient search failed").toBeTruthy();
    const { data: matches } = await search.json();
    const rohan = (matches as { id: string; full_name: string }[]).find((p) =>
      /rohan verma/i.test(p.full_name)
    );
    expect(
      rohan,
      "seeded patient 'Rohan Verma' not found — run `make seed`"
    ).toBeTruthy();

    // Self-heal across reruns: cancel any still-active queue entries a
    // previous (possibly interrupted) run left for Rohan.
    const list = await page.request.get(`${apiOrigin}/api/v1/queue`, {
      headers: authHeaders,
    });
    const { data: existing } = await list.json();
    for (const entry of existing as {
      id: string;
      patient_id: string;
      status: string;
    }[]) {
      if (
        entry.patient_id === rohan!.id &&
        (entry.status === "waiting" || entry.status === "in_consultation")
      ) {
        await page.request.patch(
          `${apiOrigin}/api/v1/queue/${entry.id}/status`,
          { headers: authHeaders, data: { status: "cancelled" } }
        );
      }
    }

    // Check Rohan in via the front-desk API (no check-in UI exists yet).
    const checkin = await page.request.post(`${apiOrigin}/api/v1/queue`, {
      headers: authHeaders,
      data: { patient_id: rohan!.id, notes: "E2E check-in" },
    });
    expect(checkin.status(), "queue check-in failed").toBe(201);

    // He now appears under "Waiting".
    await page.reload();
    const waitingSection = page.locator("section", {
      has: page.getByRole("heading", { name: /waiting/i }),
    });
    await expect(waitingSection.getByText("Rohan Verma")).toBeVisible();

    // Advance: waiting → in_consultation via the card's "Call In" button.
    // The card is the deepest div containing both the name and the button.
    const rohanCard = waitingSection
      .locator("div")
      .filter({ hasText: "Rohan Verma" })
      .filter({ has: page.getByRole("button", { name: "Call In" }) })
      .last();
    await rohanCard.getByRole("button", { name: "Call In" }).click();

    const inConsultSection = page.locator("section", {
      has: page.getByRole("heading", { name: "In Consultation" }),
    });
    await expect(inConsultSection.getByText("Rohan Verma")).toBeVisible();

    // Advance again: in_consultation → completed via the "Complete" button.
    const consultCard = inConsultSection
      .locator("div")
      .filter({ hasText: "Rohan Verma" })
      .filter({ has: page.getByRole("button", { name: "Complete" }) })
      .last();
    await consultCard.getByRole("button", { name: "Complete" }).click();

    const doneSection = page.locator("section", {
      has: page.getByRole("heading", { name: /completed today/i }),
    });
    await expect(doneSection.getByText("Rohan Verma")).toBeVisible();
  });
});
