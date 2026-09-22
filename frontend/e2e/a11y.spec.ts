import { type Page } from "@playwright/test";
import { test, expect } from "./fixtures/auth";
import { AxeBuilder } from "@axe-core/playwright";
import type { AxeResults } from "axe-core";
import * as fs from "fs";
import * as path from "path";

/**
 * Real-browser accessibility audit (axe-core via @axe-core/playwright).
 *
 * The jest-axe suite runs in jsdom, which has no layout engine — it cannot
 * evaluate `color-contrast` (needs computed styles on rendered boxes) or the
 * `region` landmark rule reliably. Running axe in real Chromium covers both.
 *
 * What each test does:
 *   1. Full `AxeBuilder.analyze()` — every default rule, including `region`
 *      (landmark coverage) and `color-contrast`.
 *   2. A dedicated `withRules(["color-contrast"])` pass so contrast failures
 *      are reported separately for triage.
 *   3. Writes a JSON report to `test-results/a11y/<page>.json` (gitignored)
 *      with every violation + node targets.
 *   4. Fails on `critical` violations only — serious/moderate findings are
 *      logged and captured in the JSON for triage instead of auto-failing,
 *      so the audit can land before the whole backlog is fixed.
 *
 * Page coverage:
 *   /                       — public landing (the login entry point; /login
 *                             itself just bounces to the Keycloak hosted
 *                             page, which is external to this codebase)
 *   /patient/appointments   — patient portal (loginAs "patient")
 *   /doctor/appointments    — doctor portal (loginAs "doctor")
 *   /admin/dashboard        — admin portal (loginAs "admin")
 *
 * Authenticated tests are tagged @auth and skip unless the matching
 * E2E_*_EMAIL/PASSWORD env vars are set — same pattern as the other e2e
 * specs.
 */

const REPORT_DIR = path.join("test-results", "a11y");

interface AuditSummary {
  page: string;
  url: string;
  violations: SerializedViolation[];
  contrastViolations: SerializedViolation[];
  counts: { critical: number; serious: number; moderate: number; minor: number };
}

interface SerializedViolation {
  id: string;
  impact: string | null | undefined;
  description: string;
  help: string;
  helpUrl: string;
  nodes: { target: unknown; failureSummary?: string }[];
}

function serialize(results: AxeResults): SerializedViolation[] {
  return results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    description: v.description,
    help: v.help,
    helpUrl: v.helpUrl,
    nodes: v.nodes.map((n) => ({
      target: n.target,
      failureSummary: n.failureSummary,
    })),
  }));
}

function countByImpact(violations: SerializedViolation[]) {
  const counts = { critical: 0, serious: 0, moderate: 0, minor: 0 };
  for (const v of violations) {
    if (v.impact && v.impact in counts) {
      counts[v.impact as keyof typeof counts] += 1;
    }
  }
  return counts;
}

/**
 * Runs both axe passes on the current page, writes the JSON triage report,
 * and returns the summary so the caller can assert on it.
 */
async function audit(page: Page, pageName: string): Promise<AuditSummary> {
  // Full ruleset: wcag2a/2aa/21a/21aa + best-practice (incl. `region`,
  // `color-contrast`, `landmark-*` rules that jsdom can't evaluate).
  const full = await new AxeBuilder({ page }).analyze();
  // Dedicated contrast pass for a standalone report section.
  const contrast = await new AxeBuilder({ page })
    .withRules(["color-contrast"])
    .analyze();

  const violations = serialize(full);
  const contrastViolations = serialize(contrast);
  const summary: AuditSummary = {
    page: pageName,
    url: page.url(),
    violations,
    contrastViolations,
    counts: countByImpact(violations),
  };

  fs.mkdirSync(REPORT_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(REPORT_DIR, `${pageName}.json`),
    JSON.stringify(summary, null, 2)
  );

  // eslint-disable-next-line no-console -- intentional triage logging
  console.log(
    `[a11y] ${pageName}: ${violations.length} violation rule(s) ` +
      `(critical=${summary.counts.critical} serious=${summary.counts.serious} ` +
      `moderate=${summary.counts.moderate} minor=${summary.counts.minor}), ` +
      `color-contrast nodes=${contrastViolations.reduce(
        (n, v) => n + v.nodes.length,
        0
      )}`
  );

  return summary;
}

function expectNoCritical(summary: AuditSummary) {
  const critical = summary.violations.filter((v) => v.impact === "critical");
  expect(
    critical,
    `critical a11y violations on ${summary.page}: ${JSON.stringify(
      critical.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
      null,
      2
    )}`
  ).toEqual([]);
}

test.describe("a11y audit — public", () => {
  test("landing page has no critical violations", async ({ page }) => {
    await page.goto("/");
    // HomeClient renders a spinner until Keycloak init resolves (or fails
    // when Keycloak is down — initAuth catches and still unblocks render).
    await expect(
      page.getByRole("heading", { name: /your health records/i })
    ).toBeVisible({ timeout: 30_000 });

    const summary = await audit(page, "landing");
    expectNoCritical(summary);
  });
});

test.describe("a11y audit — patient portal", { tag: "@auth" }, () => {
  test.beforeEach(async ({ loginAs }) => {
    await loginAs("patient");
  });

  test("patient appointments has no critical violations", async ({ page }) => {
    await page.goto("/patient/appointments");
    await expect(page.locator("main")).toBeVisible({ timeout: 30_000 });
    // Let React Query settle so axe scans real content, not skeletons.
    await page
      .waitForLoadState("networkidle", { timeout: 10_000 })
      .catch(() => {});

    const summary = await audit(page, "patient-appointments");
    expectNoCritical(summary);
  });
});

test.describe("a11y audit — doctor portal", { tag: "@auth" }, () => {
  test.beforeEach(async ({ loginAs }) => {
    await loginAs("doctor");
  });

  test("doctor appointments has no critical violations", async ({ page }) => {
    await page.goto("/doctor/appointments");
    await expect(page.locator("main")).toBeVisible({ timeout: 30_000 });
    await page
      .waitForLoadState("networkidle", { timeout: 10_000 })
      .catch(() => {});

    const summary = await audit(page, "doctor-appointments");
    expectNoCritical(summary);
  });
});

test.describe("a11y audit — admin portal", { tag: "@auth" }, () => {
  test.beforeEach(async ({ loginAs }) => {
    await loginAs("admin");
  });

  test("admin dashboard has no critical violations", async ({ page }) => {
    await page.goto("/admin/dashboard");
    await expect(page.locator("main")).toBeVisible({ timeout: 30_000 });
    await page
      .waitForLoadState("networkidle", { timeout: 10_000 })
      .catch(() => {});

    const summary = await audit(page, "admin-dashboard");
    expectNoCritical(summary);
  });
});
