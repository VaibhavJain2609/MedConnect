// Sentry edge-runtime init — imported by src/instrumentation.ts register()
// when NEXT_RUNTIME === "edge". Same pattern as sentry.server.config.ts:
// silent no-op when the DSN is unset.
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_APP_ENV || "development",
    tracesSampleRate: 0.1,
  });
}
