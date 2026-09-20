// MedConnect Service Worker v2
// Static assets only — never cache authenticated portal HTML or API responses.
const CACHE_NAME = 'medconnect-v2';
const STATIC_ASSETS = ['/', '/manifest.json'];
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

  // Navigations: network-only, fall back to the cached landing page offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/').then((r) => r || Response.error()))
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
