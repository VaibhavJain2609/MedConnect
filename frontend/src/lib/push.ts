/**
 * Web Push subscription helpers.
 *
 * Flow: fetch the VAPID public key → request notification permission →
 * subscribe via the service worker's PushManager → POST the subscription
 * (endpoint + encryption keys) to the backend, which upserts by endpoint.
 *
 * The backend returns 404 on /vapid-public when VAPID is not configured —
 * callers should treat that as "push unavailable" and hide the UI.
 */

import api from "./api";

/** Decode a base64url VAPID public key for PushManager.subscribe(). */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    bytes[i] = raw.charCodeAt(i);
  }
  return bytes;
}

export function pushSupported(): boolean {
  // Undefined-valued globals (jsdom, some webviews) fail `in` checks only —
  // compare values so a present-but-undefined property doesn't count.
  return (
    typeof window !== "undefined" &&
    typeof navigator !== "undefined" &&
    navigator.serviceWorker !== undefined &&
    window.PushManager !== undefined &&
    window.Notification !== undefined
  );
}

/**
 * Browser notification permission for this origin, or "unsupported" when
 * the Notifications API is absent. "denied" is sticky — the user must
 * re-enable notifications in browser site settings before push can work.
 */
export function getPushPermission(): NotificationPermission | "unsupported" {
  if (!pushSupported()) return "unsupported";
  return Notification.permission;
}

/** Current browser subscription, or null. */
export async function getPushSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

/**
 * Enable push on this device. Returns true when a subscription was
 * registered with the backend, false when unsupported/unconfigured/denied.
 * Throws only on unexpected failures (network, subscribe errors).
 */
export async function enablePushNotifications(): Promise<boolean> {
  if (!pushSupported()) return false;

  let publicKey: string;
  try {
    const res = await api.get("/api/v1/push/vapid-public");
    publicKey = res.data.public_key;
  } catch {
    return false; // 404 — push not configured on the server
  }
  if (!publicKey) return false;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return false;

  const reg = await navigator.serviceWorker.ready;
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
  });
  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    throw new Error("Browser returned an incomplete push subscription");
  }

  await api.post("/api/v1/push/subscribe", {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
  });
  return true;
}

/** Unsubscribe this device and delete the server-side row. */
export async function disablePushNotifications(): Promise<void> {
  const subscription = await getPushSubscription();
  if (!subscription) return;
  try {
    await api.delete("/api/v1/push/subscribe", {
      data: { endpoint: subscription.endpoint },
    });
  } catch {
    // Row may already be gone — still drop the browser subscription.
  }
  await subscription.unsubscribe();
}
