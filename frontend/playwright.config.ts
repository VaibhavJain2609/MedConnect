import { defineConfig, devices } from "@playwright/test";

/**
 * MedConnect Playwright E2E config.
 *
 * Two run modes:
 *
 * 1. Local / self-hosted mode (default): PLAYWRIGHT_BASE_URL is unset, so
 *    `webServer` boots `npm run dev` on :3000 and tests run against it.
 *    The backend + Keycloak are expected to come from `docker compose up`
 *    at the repo root — Playwright only manages the Next.js dev server.
 *
 * 2. Staging-URL mode: set PLAYWRIGHT_BASE_URL (e.g. in CI via the
 *    E2E_BASE_URL repo variable) and `webServer` is skipped entirely —
 *    tests run against whatever is already serving at that URL.
 */
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  // Retries only in CI — locally a failure should fail loudly, not flake-hide.
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  reporter: isCI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    // Runs auth.setup.ts first when E2E_TEST_EMAIL/E2E_TEST_PASSWORD are set
    // (it skips itself otherwise). Chromium depends on it so the saved
    // storage state exists before authenticated specs run.
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],
  // Only boot the dev server when aiming at localhost — in staging-URL mode
  // the target already exists and nothing needs to be spawned.
  ...(process.env.PLAYWRIGHT_BASE_URL
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: "http://localhost:3000",
          // Reuse a dev server you already have running locally; in CI a
          // fresh one is always started.
          reuseExistingServer: !isCI,
          timeout: 120_000,
        },
      }),
});
