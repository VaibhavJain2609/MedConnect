// MedConnect Service Worker v3
// Static assets + the offline fallback page — never cache authenticated
// portal HTML or API responses (PHI risk).
const CACHE_NAME = 'medconnect-v3';
const OFFLINE_URL = '/offline';
const STATIC_ASSETS = ['/', '/manifest.json', OFFLINE_URL];
const CACHEABLE_PATH =
  /^\/(_next\/(static|image)\/|icon-[^/]*\.png$|.*\.(?:css|js|woff2?|png|jpg|jpeg|svg|ico)$)/;

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => {}))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Never touch API requests
  if (url.pathname.startsWith('/api/')) return;

  // Navigations: network-only, fall back to the precached offline page.
  // Portal HTML is never cached — a stale authenticated page would leak PHI.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches
          .match(OFFLINE_URL)
          .then((r) => r || caches.match('/'))
          .then((r) => r || Response.error())
      )
    );
    return;
  }

  // Cache-first for same-origin static assets
  if (url.origin !== self.location.origin || !CACHEABLE_PATH.test(url.pathname)) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then(
      (cached) =>
        cached ||
        fetch(event.request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
    )
  );
});

// ---------------------------------------------------------------------------
// Web Push
// ---------------------------------------------------------------------------
// The backend sends {title, url} only — no body — because push payloads
// transit third-party push services and bodies could carry PHI.
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const title = data.title || 'MedConnect';
  const url = typeof data.url === 'string' && data.url ? data.url : '/';
  event.waitUntil(
    self.registration.showNotification(title, {
      icon: '/icon-192.png',
      data: { url },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url =
    (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((windowClients) => {
        // Focus an existing app tab and navigate it, else open a new one.
        for (const client of windowClients) {
          if (client.url.startsWith(self.location.origin)) {
            client.navigate(url);
            return client.focus();
          }
        }
        return clients.openWindow(url);
      })
  );
});
