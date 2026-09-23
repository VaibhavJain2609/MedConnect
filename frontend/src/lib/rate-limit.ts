/**
 * Rate-limit (HTTP 429) helpers.
 *
 * The backend `RateLimitMiddleware` (backend/app/middleware/rate_limit.py)
 * returns:
 *   status: 429
 *   body:   { "error": { "code": "RATE_LIMIT_EXCEEDED", "message": "..." } }
 *   headers:
 *     Retry-After: <seconds until the current window resets>
 *     X-RateLimit-Bucket: "ip" | "user"  (which bucket tripped)
 *
 * The axios response interceptor in src/lib/api.ts converts those errors
 * into `RateLimitError` so callers can catch a distinct type instead of
 * sniffing `error.response?.status === 429`. `userMessage` carries a
 * friendly, display-ready string — matching the existing `userMessage`
 * convention other interceptor branches set on the raw AxiosError.
 */
import type { AxiosError, InternalAxiosRequestConfig } from "axios";
import { toast } from "@/hooks/use-toast";

/** Only auto-retry when the server asks for a wait this short (seconds). */
export const RATE_LIMIT_AUTO_RETRY_MAX_SECONDS = 10;

/** Config flag marking that a request already consumed its one retry. */
export const RATE_LIMIT_RETRY_FLAG = "__rateLimitRetried";

type RateLimitBucket = "ip" | "user";

export class RateLimitError extends Error {
  readonly name = "RateLimitError";
  readonly status = 429;
  /** Seconds the server asked us to wait, or null when it didn't say. */
  readonly retryAfter: number | null;
  /** Which limit tripped: "ip" (per-caller) or "user" (per-account). */
  readonly bucket: RateLimitBucket | null;
  /** Friendly display string — same convention as AxiosError.userMessage. */
  userMessage: string;
  /** Original axios response/config for callers that still inspect them. */
  readonly response: AxiosError["response"];
  readonly config: AxiosError["config"];

  constructor(error: AxiosError, retryAfter: number | null, bucket: RateLimitBucket | null) {
    super("Too many requests");
    this.retryAfter = retryAfter;
    this.bucket = bucket;
    this.response = error.response;
    this.config = error.config;
    this.userMessage = rateLimitMessage(retryAfter);
    // Preserve the chain for debugging / Sentry.
    this.cause = error;
  }
}

export function isRateLimitError(err: unknown): err is RateLimitError {
  return err instanceof RateLimitError;
}

/**
 * English fallback message for non-React contexts (the same convention the
 * interceptor already uses for 403/404/5xx `userMessage`s). React surfaces
 * localize via the `common.rateLimited*` keys in messages/*.json.
 */
export function rateLimitMessage(retryAfter: number | null): string {
  return retryAfter != null
    ? `Too many requests — try again in ${retryAfter}s`
    : "Too many requests — please try again shortly";
}

type HeaderGetter = (name: string) => string | null | undefined;

function headerGetter(headers: unknown): HeaderGetter {
  if (!headers) return () => undefined;
  // AxiosHeaders exposes .get(); plain objects (mocks, XHR pre-1.x) don't.
  if (typeof (headers as { get?: unknown }).get === "function") {
    return (name) => (headers as { get: (n: string) => string | null | undefined }).get(name);
  }
  const obj = headers as Record<string, string | undefined>;
  return (name) => obj[name] ?? obj[name.toLowerCase()];
}

/**
 * Parse the seconds-until-retry from response headers.
 * Prefers `Retry-After` (delta-seconds or HTTP-date, per RFC 9110), then
 * falls back to `X-RateLimit-Reset` (absolute epoch seconds) if present.
 */
export function parseRetryAfter(headers: unknown, now: number = Date.now()): number | null {
  const get = headerGetter(headers);

  const retryAfter = get("Retry-After");
  if (retryAfter != null && retryAfter !== "") {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds)) {
      return Math.max(0, Math.ceil(seconds));
    }
    // HTTP-date form
    const dateMs = Date.parse(retryAfter);
    if (Number.isFinite(dateMs)) {
      return Math.max(0, Math.ceil((dateMs - now) / 1000));
    }
  }

  const reset = get("X-RateLimit-Reset");
  if (reset != null && reset !== "") {
    const epoch = Number(reset);
    if (Number.isFinite(epoch)) {
      return Math.max(0, Math.ceil(epoch - now / 1000));
    }
  }

  return null;
}

function parseBucket(headers: unknown): RateLimitBucket | null {
  const value = headerGetter(headers)("X-RateLimit-Bucket");
  return value === "ip" || value === "user" ? value : null;
}

/** Convert a 429 AxiosError into a typed RateLimitError. */
export function toRateLimitError(error: AxiosError): RateLimitError {
  const headers = error.response?.headers;
  return new RateLimitError(error, parseRetryAfter(headers), parseBucket(headers));
}

const IDEMPOTENT_METHODS = new Set(["get", "head"]);

/**
 * Auto-retry policy: a single transparent retry, only for idempotent
 * GET/HEAD requests, only when the server said how long to wait and the
 * wait is short enough not to stall the UI.
 */
export function shouldAutoRetry(
  config: InternalAxiosRequestConfig | undefined,
  retryAfter: number | null
): boolean {
  if (!config) return false;
  const flagged = config as InternalAxiosRequestConfig & {
    [RATE_LIMIT_RETRY_FLAG]?: boolean;
  };
  if (flagged[RATE_LIMIT_RETRY_FLAG]) return false;
  if (!IDEMPOTENT_METHODS.has((config.method ?? "").toLowerCase())) return false;
  return retryAfter != null && retryAfter >= 0 && retryAfter <= RATE_LIMIT_AUTO_RETRY_MAX_SECONDS;
}

export function markRetried(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  (config as InternalAxiosRequestConfig & { [RATE_LIMIT_RETRY_FLAG]?: boolean })[
    RATE_LIMIT_RETRY_FLAG
  ] = true;
  return config;
}

// ---------------------------------------------------------------------------
// Global surfacing
// ---------------------------------------------------------------------------

/** Collapse bursts of simultaneous 429s (parallel queries/mutations) into
 *  one toast instead of N stacked identical toasts. */
const TOAST_DEDUPE_MS = 5000;
let _lastRateLimitToastAt = 0;

interface RateLimitToastCopy {
  title: string;
  describe: (retryAfter: number | null) => string;
}

/** Localized toast copy, registered by Providers once mounted so the
 *  transport layer can toast in the user's language. Falls back to the
 *  English `userMessage` before registration (and on the server). */
let _toastCopy: RateLimitToastCopy | null = null;

export function setRateLimitToastCopy(copy: RateLimitToastCopy | null): void {
  _toastCopy = copy;
}

/**
 * Show a single deduped "Too many requests" toast. Called by the axios
 * interceptor for every rejected 429 — the one global surfacing point,
 * covering React Query calls and raw `api.*` calls alike.
 */
export function notifyRateLimited(error: RateLimitError): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  if (now - _lastRateLimitToastAt < TOAST_DEDUPE_MS) return;
  _lastRateLimitToastAt = now;

  toast({
    title: _toastCopy?.title ?? "Too many requests",
    description: _toastCopy?.describe(error.retryAfter) ?? error.userMessage,
    variant: "destructive",
  });
}

/** Test-only: reset the toast dedupe window between specs. */
export function _resetRateLimitToastDedupe(): void {
  _lastRateLimitToastAt = 0;
}
