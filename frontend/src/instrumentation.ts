// Next.js instrumentation hook — runs once per runtime on server startup.
// Enabled via `experimental.instrumentationHook` in next.config.js
// (required on Next 14; stable without the flag on Next 15+).
// Loads the Sentry init files manually since we don't use withSentryConfig.
export async function register() {
  // Skip entirely when Sentry isn't configured — keeps local dev clean.
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) return;

  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }
}
