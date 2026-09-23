/**
 * Tests for the 429/rate-limit handling in src/lib/rate-limit.ts and the
 * axios interceptor transform in src/lib/api.ts.
 *
 * The interceptor is exercised end-to-end by swapping `api.defaults.adapter`
 * for a stub that replays canned 429/200 responses — `keycloak-js` is
 * auto-mocked in tests/setup.ts so the request interceptor is a no-op.
 */
import type { AxiosResponse, InternalAxiosRequestConfig } from "axios";
import api from "@/lib/api";
import {
  _resetRateLimitToastDedupe,
  isRateLimitError,
  parseRetryAfter,
  RateLimitError,
  rateLimitMessage,
  shouldAutoRetry,
  toRateLimitError,
} from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function rateLimitedResponse(
  config: InternalAxiosRequestConfig,
  headers: Record<string, string> = { "Retry-After": "30", "X-RateLimit-Bucket": "ip" }
) {
  const err = Object.assign(new Error("Request failed with status code 429"), {
    isAxiosError: true,
    code: "ERR_BAD_RESPONSE",
    config,
    response: {
      status: 429,
      statusText: "Too Many Requests",
      headers,
      data: {
        error: {
          code: "RATE_LIMIT_EXCEEDED",
          message: "Rate limit exceeded. Maximum 20 write requests per minute.",
        },
      },
      config,
    },
  });
  return Promise.reject(err);
}

function okResponse(config: InternalAxiosRequestConfig, data: unknown = { ok: true }) {
  const response: AxiosResponse = {
    status: 200,
    statusText: "OK",
    headers: {},
    data,
    config,
  };
  return Promise.resolve(response);
}

beforeEach(() => {
  _resetRateLimitToastDedupe();
});

// ---------------------------------------------------------------------------
// parseRetryAfter
// ---------------------------------------------------------------------------

describe("parseRetryAfter", () => {
  it("parses delta-seconds from Retry-After", () => {
    expect(parseRetryAfter({ "Retry-After": "30" })).toBe(30);
    expect(parseRetryAfter({ "retry-after": "7.4" })).toBe(8);
  });

  it("parses HTTP-date Retry-After relative to now", () => {
    const now = Date.now();
    const httpDate = new Date(now + 20_000).toUTCString();
    const parsed = parseRetryAfter({ "Retry-After": httpDate }, now);
    expect(parsed).not.toBeNull();
    expect(parsed!).toBeGreaterThanOrEqual(19);
    expect(parsed!).toBeLessThanOrEqual(20);
  });

  it("clamps past HTTP-dates to 0", () => {
    const now = Date.now();
    const past = new Date(now - 5_000).toUTCString();
    expect(parseRetryAfter({ "Retry-After": past }, now)).toBe(0);
  });

  it("falls back to X-RateLimit-Reset epoch seconds", () => {
    const now = Date.now();
    const resetEpoch = Math.floor(now / 1000) + 12;
    const parsed = parseRetryAfter({ "X-RateLimit-Reset": String(resetEpoch) }, now);
    expect(parsed).not.toBeNull();
    expect(parsed!).toBeGreaterThanOrEqual(11);
    expect(parsed!).toBeLessThanOrEqual(12);
  });

  it("supports AxiosHeaders-style .get()", () => {
    const headers = { get: (name: string) => (name === "Retry-After" ? "5" : null) };
    expect(parseRetryAfter(headers)).toBe(5);
  });

  it("returns null when no headers are usable", () => {
    expect(parseRetryAfter(undefined)).toBeNull();
    expect(parseRetryAfter({})).toBeNull();
    expect(parseRetryAfter({ "Retry-After": "not-a-number-or-date" })).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// toRateLimitError / RateLimitError
// ---------------------------------------------------------------------------

describe("toRateLimitError", () => {
  it("carries retryAfter, bucket and a friendly userMessage", () => {
    const error = {
      response: {
        status: 429,
        headers: { "Retry-After": "30", "X-RateLimit-Bucket": "user" },
      },
      config: { method: "post" },
    } as any;

    const rl = toRateLimitError(error);
    expect(rl).toBeInstanceOf(RateLimitError);
    expect(isRateLimitError(rl)).toBe(true);
    expect(rl.status).toBe(429);
    expect(rl.retryAfter).toBe(30);
    expect(rl.bucket).toBe("user");
    expect(rl.userMessage).toBe("Too many requests — try again in 30s");
    expect(rl.response).toBe(error.response);
  });

  it("produces a generic message when Retry-After is absent", () => {
    const error = {
      response: { status: 429, headers: {} },
      config: { method: "get" },
    } as any;
    const rl = toRateLimitError(error);
    expect(rl.retryAfter).toBeNull();
    expect(rl.userMessage).toBe("Too many requests — please try again shortly");
  });
});

describe("rateLimitMessage", () => {
  it("includes the wait when known", () => {
    expect(rateLimitMessage(12)).toBe("Too many requests — try again in 12s");
  });
  it("falls back to a generic message", () => {
    expect(rateLimitMessage(null)).toBe(
      "Too many requests — please try again shortly"
    );
  });
});

// ---------------------------------------------------------------------------
// shouldAutoRetry
// ---------------------------------------------------------------------------

describe("shouldAutoRetry", () => {
  const cfg = (method: string, extra: Record<string, unknown> = {}) =>
    ({ method, headers: {}, ...extra }) as unknown as InternalAxiosRequestConfig;

  it("allows a single retry for GET/HEAD within the cap", () => {
    expect(shouldAutoRetry(cfg("get"), 5)).toBe(true);
    expect(shouldAutoRetry(cfg("GET"), 10)).toBe(true);
    expect(shouldAutoRetry(cfg("head"), 0)).toBe(true);
  });

  it("refuses non-idempotent methods", () => {
    expect(shouldAutoRetry(cfg("post"), 5)).toBe(false);
    expect(shouldAutoRetry(cfg("put"), 5)).toBe(false);
    expect(shouldAutoRetry(cfg("delete"), 5)).toBe(false);
  });

  it("refuses when the wait exceeds the cap or is unknown", () => {
    expect(shouldAutoRetry(cfg("get"), 11)).toBe(false);
    expect(shouldAutoRetry(cfg("get"), null)).toBe(false);
  });

  it("refuses a request that already consumed its retry", () => {
    expect(
      shouldAutoRetry(cfg("get", { __rateLimitRetried: true }), 5)
    ).toBe(false);
  });

  it("refuses without a config", () => {
    expect(shouldAutoRetry(undefined, 5)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Interceptor behaviour (real axios instance, stubbed adapter)
// ---------------------------------------------------------------------------

describe("api interceptor 429 handling", () => {
  afterEach(() => {
    delete (api.defaults as { adapter?: unknown }).adapter;
  });

  it("rejects a non-idempotent request with a typed RateLimitError", async () => {
    const adapter = jest.fn((config: InternalAxiosRequestConfig) =>
      rateLimitedResponse(config)
    );
    api.defaults.adapter = adapter;

    await expect(api.post("/api/v1/uploads/presign", {})).rejects.toMatchObject({
      name: "RateLimitError",
      status: 429,
      retryAfter: 30,
      bucket: "ip",
      userMessage: "Too many requests — try again in 30s",
    });
    expect(adapter).toHaveBeenCalledTimes(1); // no retry for POST
  });

  it("transparently retries an idempotent GET once after a short Retry-After", async () => {
    const adapter = jest
      .fn()
      .mockImplementationOnce((config: InternalAxiosRequestConfig) =>
        rateLimitedResponse(config, { "Retry-After": "0" })
      )
      .mockImplementationOnce((config: InternalAxiosRequestConfig) =>
        okResponse(config)
      );
    api.defaults.adapter = adapter;

    const res = await api.get("/api/v1/search");
    expect(res.data).toEqual({ ok: true });
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it("does not retry a GET when Retry-After exceeds the cap", async () => {
    const adapter = jest.fn((config: InternalAxiosRequestConfig) =>
      rateLimitedResponse(config, { "Retry-After": "30" })
    );
    api.defaults.adapter = adapter;

    await expect(api.get("/api/v1/search")).rejects.toBeInstanceOf(
      RateLimitError
    );
    expect(adapter).toHaveBeenCalledTimes(1);
  });

  it("only retries once — a second 429 surfaces as RateLimitError", async () => {
    const adapter = jest.fn((config: InternalAxiosRequestConfig) =>
      rateLimitedResponse(config, { "Retry-After": "0" })
    );
    api.defaults.adapter = adapter;

    await expect(api.get("/api/v1/search")).rejects.toMatchObject({
      name: "RateLimitError",
      retryAfter: 0,
    });
    expect(adapter).toHaveBeenCalledTimes(2);
  });
});
