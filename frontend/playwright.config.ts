import { defineConfig, devices } from "@playwright/test";

/**
 * MedConnect Playwright E2E config.
 *
 * Two run modes:
 *
 * 1. Local / full-stack mode (default): PLAYWRIGHT_BASE_URL is unset, so
 *    `webServer` serves the app on :3000 — `next dev` locally, `next start`
 *    in CI (the workflow runs `npm run build` first). The backend +
 *    Keycloak are expected to come from `docker compose up` at the repo
 *    root (CI: postgres/redis/keycloak via compose, backend via uvicorn
 *    on the runner) plus `make seed` for the demo dataset.
 *
 * 2. Staging-URL mode: set PLAYWRIGHT_BASE_URL (e.g. in CI via the
 *    E2E_BASE_URL repo variable) and `webServer` is skipped entirely —
 *    tests run against whatever is already serving at that URL.
 *
 * Authentication: specs tagged @auth use the direct-grant fixture in
 * e2e/fixtures/auth.ts — it mints real Keycloak tokens and injects them
 * before app boot. They skip when the role's E2E_*_EMAIL/PASSWORD env
 * vars are unset; `--grep-invert @auth` excludes them wholesale.
 */
// `||` not `??`: the CI workflow exports PLAYWRIGHT_BASE_URL as an empty
// string when vars.E2E_BASE_URL is unset, and "" must mean "local mode".
const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
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
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Only boot a server when aiming at localhost — in staging-URL mode the
  // target already exists and nothing needs to be spawned. In CI the
  // workflow builds the app (`npm run build`) ahead of this, so `next
  // start` serves the production bundle: no per-request dev compilation
  // to race the specs' timeouts.
  ...(process.env.PLAYWRIGHT_BASE_URL
    ? {}
    : {
        webServer: {
          command: isCI ? "npm run start" : "npm run dev",
          url: "http://localhost:3000",
          // Reuse a dev server you already have running locally; in CI a
          // fresh one is always started.
          reuseExistingServer: !isCI,
          timeout: 120_000,
        },
      }),
});
