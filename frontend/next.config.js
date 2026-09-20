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
    // TODO(security): tighten for production — replace 'unsafe-eval' /
    // 'unsafe-inline' in script-src with nonces once Next.js nonce plumbing
    // is in place ('unsafe-eval' is required by the Next 14 dev runtime).
    const connectSrc = [
      "'self'",
      cspOrigin(process.env.NEXT_PUBLIC_API_URL),
      cspOrigin(process.env.NEXT_PUBLIC_KEYCLOAK_URL),
      'ws:', 'wss:', // Next.js HMR websocket (dev)
    ].filter(Boolean).join(' ');
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'geolocation=(), microphone=(), camera=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self' data:",
              `connect-src ${connectSrc}`,
              // 'none' is consistent with X-Frame-Options: DENY above.
              "frame-ancestors 'none'",
              "object-src 'none'",
              "base-uri 'self'",
            ].join('; '),
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
