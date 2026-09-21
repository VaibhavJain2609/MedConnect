"use client";

// Side-effect import: runs Sentry.init() in the browser bundle.
// Guarded inside sentry.client.config.ts — no-op unless
// NEXT_PUBLIC_SENTRY_DSN is set.
import "../../sentry.client.config";

// Renderless client component mounted once in the root layout so the
// Sentry browser SDK initializes before any page code runs.
export function SentryInit() {
  return null;
}
