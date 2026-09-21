// Next.js instrumentation hook — runs once per runtime on server startup.
// Stable since Next 15 (no config flag needed on 15+; the old
// experimental.instrumentationHook flag was removed on upgrade to Next 16).
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
