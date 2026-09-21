// Sentry client-side init — Next.js 14 convention.
// Loaded manually via src/components/sentry-init.tsx (rendered in the root
// layout). We deliberately do NOT use withSentryConfig: the wrapper's main
// job is wiring the webpack plugin for sourcemap upload + auto-instrumentation,
// neither of which we want (no SENTRY_AUTH_TOKEN in CI; keep the build light).
// Manual init keeps Sentry a silent no-op whenever the DSN is unset.
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    // Mirrors backend convention: SENTRY_DSN unset => SDK never initialized.
    environment: process.env.NEXT_PUBLIC_APP_ENV || "development",
    // 10% trace sampling, same as backend/app/main.py.
    tracesSampleRate: 0.1,
  });
}
