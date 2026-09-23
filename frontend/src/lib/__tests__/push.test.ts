/**
 * Tests for src/lib/push.ts — pushSupported() and getPushPermission().
 * jsdom lacks serviceWorker/PushManager/Notification, so each case stubs
 * the globals it needs and restores them afterwards.
 */

import { getPushPermission, pushSupported } from "../push";

type PushGlobals = {
  serviceWorker: unknown;
  PushManager: unknown;
  Notification: unknown;
};

const originals: PushGlobals = {
  serviceWorker: undefined,
  PushManager: undefined,
  Notification: undefined,
};

beforeEach(() => {
  originals.serviceWorker = (navigator as { serviceWorker?: unknown })
    .serviceWorker;
  originals.PushManager = (window as { PushManager?: unknown }).PushManager;
  originals.Notification = (window as { Notification?: unknown }).Notification;
});

afterEach(() => {
  Object.defineProperty(window.navigator, "serviceWorker", {
    value: originals.serviceWorker,
    configurable: true,
    writable: true,
  });
  (window as { PushManager?: unknown }).PushManager = originals.PushManager;
  (window as { Notification?: unknown }).Notification = originals.Notification;
});

function stubPushApis(permission: NotificationPermission) {
  Object.defineProperty(window.navigator, "serviceWorker", {
    value: { ready: Promise.resolve({}) },
    configurable: true,
  });
  (window as { PushManager?: unknown }).PushManager = function PushManager() {};
  (window as { Notification?: unknown }).Notification = { permission };
}

describe("pushSupported", () => {
  it("returns false when push globals are absent", () => {
    expect(pushSupported()).toBe(false);
  });

  it("returns true when serviceWorker, PushManager and Notification exist", () => {
    stubPushApis("default");
    expect(pushSupported()).toBe(true);
  });
});

describe("getPushPermission", () => {
  it('returns "unsupported" when push globals are absent', () => {
    expect(getPushPermission()).toBe("unsupported");
  });

  it.each(["default", "granted", "denied"] as const)(
    'returns "%s" straight from Notification.permission',
    (permission) => {
      stubPushApis(permission);
      expect(getPushPermission()).toBe(permission);
    }
  );
});
