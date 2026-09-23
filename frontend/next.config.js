// next-intl plugin — links src/i18n/request.ts (getRequestConfig) to the
// server/client i18n plumbing. No [locale] routing: locale comes from the
// NEXT_LOCALE cookie. See docs/i18n.md.
const createNextIntlPlugin = require("next-intl/plugin");
const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// Normalize an env URL (e.g. NEXT_PUBLIC_API_URL) to its origin so it can be
// used as a CSP source. Returns '' for unset/invalid values so callers can
// filter it out of the directive.
function cspOrigin(url) {
  if (!url) return '';
  try {
    return new URL(url).origin;
  } catch {
    return url; // already a bare host/scheme source
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // src/instrumentation.ts (Sentry server/edge init) is loaded automatically —
  // the experimental.instrumentationHook flag was removed once the hook went
  // stable (Next 15+).
  // NOTE: we intentionally do NOT wrap this config in Sentry's
  // withSentryConfig — its webpack plugin exists mainly for sourcemap
  // upload (needs SENTRY_AUTH_TOKEN, which CI doesn't have) and it also
  // auto-instruments route handlers/server functions. Manual init via
  // instrumentation.ts + the sentry.*.config.ts files is the less
  // fragile path for this codebase.
  async rewrites() {
    // k8s exposes the backend service on port 80 — allow override via env
    const apiInternalUrl = process.env.API_INTERNAL_URL || 'http://backend:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${apiInternalUrl}/api/:path*`,
      },
    ];
  },
  async headers() {
    // Content-Security-Policy is owned HERE — the single source of truth.
    // Next.js serves the app behind nginx/ALB in every deployment mode
    // (standalone, docker-compose, k8s); nginx proxies through and must NOT
    // set its own CSP (dual sources drift — that caused the CSP regression).
    // X-XSS-Protection is obsolete and omitted intentionally.
    //
    // The enforced policy still needs 'unsafe-eval'/'unsafe-inline' in
    // script-src ('unsafe-eval' is required by the Next dev runtime and
    // Next injects inline bootstrap scripts in prod too). The
    // Content-Security-Policy-Report-Only header below carries the
    // stricter nonce-ready target policy — no report-uri/report-to is set
    // because there is no collector endpoint yet; violations surface in
    // devtools/Network only. Enforcement path is documented in RUNBOOK.md
    // (Security headers & CSP section).
    const keycloakOrigin = cspOrigin(process.env.NEXT_PUBLIC_KEYCLOAK_URL);
    const isDev = process.env.NODE_ENV === 'development';
    const connectSrc = [
      "'self'",
      cspOrigin(process.env.NEXT_PUBLIC_API_URL),
      keycloakOrigin,
      // Sentry ingest origin (derived from the DSN's host) so the browser
      // SDK can POST error envelopes — silently dropped by CSP otherwise.
      cspOrigin(process.env.NEXT_PUBLIC_SENTRY_DSN),
      // Next.js HMR websockets — dev only; bare ws:/wss: schemes in prod CSP
      // would let injected scripts exfiltrate over arbitrary websockets.
      ...(process.env.NODE_ENV !== 'production' ? ['ws:', 'wss:'] : []),
    ].filter(Boolean).join(' ');
    // Directives shared by the enforced and report-only policies. Order is
    // irrelevant to the CSP grammar — script-src is prepended per-policy.
    const policyBase = [
      "default-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      `connect-src ${connectSrc}`,
      // 'none' is consistent with X-Frame-Options: DENY below.
      "frame-ancestors 'none'",
      // keycloak-js silent check-sso runs inside a hidden iframe that loads
      // the Keycloak authorize endpoint, then redirects back to
      // /silent-check-sso.html — both origins must be frame-src'd or the
      // session check is silently blocked (checkLoginIframe is disabled,
      // so this authorize iframe is the only Keycloak frame).
      ["frame-src 'self'", keycloakOrigin].filter(Boolean).join(' '),
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      // /sw.js (PWA + web-push) and /manifest.json are same-origin.
      "worker-src 'self'",
      "manifest-src 'self'",
    ];
    const enforcedCsp = [
      "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
      ...policyBase,
    ].join('; ');
    // Dry-run of the nonce-ready end state: identical to the enforced
    // policy minus the unsafe-* script concessions. Skipped under `next
    // dev` — the dev runtime cannot satisfy it and the console noise would
    // drown real signal (jest runs with NODE_ENV=test and still gets it).
    const reportOnlyCsp = [
      "script-src 'self'",
      ...policyBase,
    ].join('; ');
    const headers = [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      // Jitsi teleconsult runs on Jitsi's own domain via an external link,
      // so camera/mic stay off on our origin. No payment flows in-browser.
      {
        key: 'Permissions-Policy',
        value: 'camera=(), microphone=(), geolocation=(), payment=()',
      },
      { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
      { key: 'Content-Security-Policy', value: enforcedCsp },
    ];
    if (!isDev) {
      headers.push({
        key: 'Content-Security-Policy-Report-Only',
        value: reportOnlyCsp,
      });
    }
    return [
      {
        source: '/:path*',
        headers,
      },
    ];
  },
};

module.exports = withNextIntl(nextConfig);
