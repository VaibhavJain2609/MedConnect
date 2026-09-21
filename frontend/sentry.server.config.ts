// Sentry server-side init (Node.js runtime) — imported by
// src/instrumentation.ts register(). Silent no-op when the DSN is unset,
// mirroring backend/app/main.py's `if settings.SENTRY_DSN:` guard.
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_APP_ENV || "development",
    tracesSampleRate: 0.1,
  });
}
