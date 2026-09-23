/**
 * Contract test for the security headers emitted by next.config.js
 * headers(). Guards the CSP shape so a refactor can't silently drop
 * frame-ancestors / form-action, reintroduce a collector-less report-uri,
 * or weaken the report-only target policy.
 */

// next-intl's plugin entry does `createRequire('http://localhost/plugin.cjs')`
// which jest's module registry rejects — mock it as a passthrough wrapper so
// we exercise the real headers() logic.
jest.mock('next-intl/plugin', () => () => (config: unknown) => config);

// next.config.js is CommonJS — require() it so we test the real object.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const nextConfig = require('../../next.config.js');

type Env = Record<string, string | undefined>;

/** Call nextConfig.headers() with the given env vars applied, restored after. */
async function headerMap(env: Env = {}): Promise<Map<string, string>> {
  const saved: Env = {};
  for (const [k, v] of Object.entries(env)) {
    saved[k] = process.env[k];
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    const rules = await nextConfig.headers();
    const rule = rules.find(
      (r: { source: string }) => r.source === '/:path*'
    );
    expect(rule).toBeDefined();
    return new Map<string, string>(
      rule.headers.map((h: { key: string; value: string }) => [h.key, h.value])
    );
  } finally {
    for (const [k, v] of Object.entries(saved)) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

describe('next.config.js security headers', () => {
  it('emits the baseline hardening set on every response', async () => {
    const headers = await headerMap();
    expect(headers.get('X-Content-Type-Options')).toBe('nosniff');
    expect(headers.get('X-Frame-Options')).toBe('DENY');
    expect(headers.get('Referrer-Policy')).toBe(
      'strict-origin-when-cross-origin'
    );
    expect(headers.get('Strict-Transport-Security')).toContain('max-age=');
    const pp = headers.get('Permissions-Policy') ?? '';
    // Jitsi teleconsult is an external link, so device sensors and the
    // Payment Request API stay fully off on our origin.
    for (const feature of ['camera', 'microphone', 'geolocation', 'payment']) {
      expect(pp).toContain(`${feature}=()`);
    }
    // Deprecated — must never come back.
    expect(headers.has('X-XSS-Protection')).toBe(false);
  });

  it('enforces a CSP with clickjacking/form/object lockdowns', async () => {
    const headers = await headerMap();
    const csp = headers.get('Content-Security-Policy') ?? '';
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self' 'unsafe-eval' 'unsafe-inline'");
    expect(csp).toContain("style-src 'self' 'unsafe-inline'");
    expect(csp).toContain("img-src 'self' data: blob:");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
    expect(csp).toContain("worker-src 'self'");
    expect(csp).toContain("manifest-src 'self'");
  });

  it('derives connect-src/frame-src origins from NEXT_PUBLIC_* env vars', async () => {
    const headers = await headerMap({
      NEXT_PUBLIC_API_URL: 'https://api.example.com',
      NEXT_PUBLIC_KEYCLOAK_URL: 'https://sso.example.com',
      NEXT_PUBLIC_SENTRY_DSN: 'https://abc@o1.ingest.sentry.io/1',
    });
    const csp = headers.get('Content-Security-Policy') ?? '';
    expect(csp).toContain('https://api.example.com');
    expect(csp).toContain('https://sso.example.com');
    expect(csp).toContain('https://o1.ingest.sentry.io');
    // The keycloak-js silent check-sso iframe must be able to load the
    // Keycloak authorize endpoint.
    expect(csp).toMatch(/frame-src 'self' https:\/\/sso\.example\.com/);
  });

  it('emits the stricter report-only CSP outside development', async () => {
    // NODE_ENV is 'test' under jest — the report-only header is skipped
    // only for `next dev`.
    const headers = await headerMap();
    const reportOnly =
      headers.get('Content-Security-Policy-Report-Only') ?? '';
    expect(reportOnly).not.toBe('');
    // Nonce-ready target: same policy minus the unsafe script concessions.
    const scriptSrc = reportOnly
      .split(';')
      .map((d) => d.trim())
      .find((d) => d.startsWith('script-src'));
    expect(scriptSrc).toBe("script-src 'self'");
    // No collector endpoint exists yet — never emit a dead report target.
    for (const value of Array.from(headers.values())) {
      expect(value).not.toContain('report-uri');
      expect(value).not.toContain('report-to');
    }
  });

  it('omits the report-only CSP under `next dev` (console-noise guard)', async () => {
    const headers = await headerMap({ NODE_ENV: 'development' });
    expect(headers.has('Content-Security-Policy')).toBe(true);
    expect(headers.has('Content-Security-Policy-Report-Only')).toBe(false);
    // Dev still needs ws:/wss: in connect-src for HMR.
    expect(headers.get('Content-Security-Policy')).toContain('ws:');
  });
});
