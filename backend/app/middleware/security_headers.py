"""HTTP security-header middleware — the backend's single source of truth.

Mirrored for the frontend by ``headers()`` in ``frontend/next.config.js``;
nginx and the ALB deliberately do NOT inject response headers (see the
comment blocks in ``nginx/nginx.conf`` and
``infra/k8s/base/ingress/ingress.yaml``) — each surface owns its own so
there is no duplicate/conflicting-header drift.

Applied to every HTTP response — including error, rate-limit (429) and
maintenance-mode rejections — because this middleware wraps ``send`` at
the pure-ASGI level rather than going through ``BaseHTTPMiddleware``
(which also avoids response buffering and the contextvar-copy problem
documented in ``audit_middleware.py``).

Header set:

- ``X-Content-Type-Options: nosniff`` — block MIME sniffing.
- ``X-Frame-Options: DENY`` — legacy clickjacking guard; superseded by
  CSP ``frame-ancestors 'none'`` in modern browsers, kept for old clients.
- ``Referrer-Policy: strict-origin-when-cross-origin``.
- ``Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()``
  — the API never needs device sensors or the Payment Request API.
  Teleconsult runs on Jitsi's own domain via an external ``meeting_url``
  link (not an embedded iframe), so no camera/mic delegation is needed on
  our origin; no in-browser payment flow exists either.
- ``Content-Security-Policy`` — strict API policy: this service returns
  JSON, not HTML, so every content source is ``'none'`` except
  ``connect-src`` (kept for any future browsable resource).
- ``Strict-Transport-Security`` — production only (``APP_ENV``). Browsers
  ignore HSTS received over plain HTTP, but gating keeps intent explicit
  and matches the frontend's conditional model.
- ``Cache-Control: no-store`` + ``Pragma: no-cache`` on ``/api/v1/*`` —
  PHI must never be stored by shared caches (CDNs, corporate proxies,
  browser disk cache). ``Pragma`` covers HTTP/1.0 intermediaries that do
  not honour ``Cache-Control``. Non-API probes (/health, /livez, /metrics)
  and docs keep default cache semantics.

``X-XSS-Protection`` is intentionally absent — deprecated and known to
introduce vulnerabilities in older browsers.
"""
from starlette.datastructures import MutableHeaders

from app.config import settings

# PHI-bearing API surface — must not be cached by shared caches.
_NO_STORE_PREFIX = "/api/v1"


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        no_store = path.startswith(_NO_STORE_PREFIX)

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=(), payment=()"
                )
                # API-level CSP: strict policy for JSON/REST responses.
                # No unsafe-inline — the backend serves data, not HTML/JS/CSS.
                # frame-ancestors supersedes X-Frame-Options in modern browsers.
                headers["Content-Security-Policy"] = (
                    "default-src 'none'; "
                    "script-src 'none'; "
                    "style-src 'none'; "
                    "img-src 'none'; "
                    "font-src 'none'; "
                    f"connect-src 'self' {settings.FRONTEND_URL}; "
                    "frame-ancestors 'none';"
                )
                if no_store:
                    headers["Cache-Control"] = "no-store"
                    headers["Pragma"] = "no-cache"
                if settings.APP_ENV == "production":
                    headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
